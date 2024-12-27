import os
import logging
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Response, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydub import AudioSegment
import uvicorn
from typing import Optional
import shutil
import aiofiles

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio Overlay API")

# Create base directory for file processing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Ensure directories exist with proper permissions
def ensure_directories():
    """Create necessary directories if they don't exist"""
    try:
        os.makedirs(TEMP_DIR, mode=0o777, exist_ok=True)
        os.makedirs(OUTPUT_DIR, mode=0o777, exist_ok=True)
        logger.info(f"Directories created/verified: {TEMP_DIR}, {OUTPUT_DIR}")
    except Exception as e:
        logger.error(f"Error creating directories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server configuration error: {str(e)}")

# Call this when the app starts
ensure_directories()

def verify_audio(file_path: str) -> bool:
    """Verify if an audio file is valid and has content"""
    try:
        audio = AudioSegment.from_file(file_path)
        duration = len(audio)
        logger.info(f"Audio file {file_path} verified: duration = {duration}ms")
        return duration > 0
    except Exception as e:
        logger.error(f"Error verifying audio file {file_path}: {str(e)}")
        return False

async def save_upload_file_async(upload_file: UploadFile) -> str:
    """Save uploaded file asynchronously and return the path"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{upload_file.filename}"
        temp_file_path = os.path.join(TEMP_DIR, filename)
        
        logger.info(f"Saving file to: {temp_file_path}")
        
        # Use aiofiles for async file operations
        async with aiofiles.open(temp_file_path, "wb") as buffer:
            # Read the file in chunks
            while content := await upload_file.read(1024 * 1024):  # 1MB chunks
                await buffer.write(content)
        
        logger.info(f"File saved successfully: {temp_file_path}")
        return temp_file_path
    except Exception as e:
        logger.error(f"Error saving file {upload_file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving uploaded file: {str(e)}")

def cleanup_files(*files):
    """Clean up temporary files"""
    for file in files:
        try:
            if file and os.path.exists(file):
                os.remove(file)
                logger.info(f"Cleaned up file: {file}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file}: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Return a simple HTML form for file upload"""
    return '''
    <html>
        <body>
            <h1>Audio Overlay Tool</h1>
            <form action="/overlay/" enctype="multipart/form-data" method="post">
                <p>Speech/Vocals file: <input type="file" name="speech_file"></p>
                <p>Background Music file: <input type="file" name="music_file"></p>
                <p>Music Volume Adjustment (dB): <input type="number" name="music_volume_adjustment" value="-10"></p>
                <p>Fade In Duration (seconds): <input type="number" name="fade_in_duration" value="3"></p>
                <p>Fade Out Duration (seconds): <input type="number" name="fade_out_duration" value="3"></p>
                <input type="submit" value="Upload and Process">
            </form>
        </body>
    </html>
    '''

@app.post("/overlay/")
@app.post("/overlay")
async def create_overlay(
    request: Request,
    speech_file: UploadFile = File(...),
    music_file: UploadFile = File(...),
    music_volume_adjustment: int = -10,
    speech_start: int = 0,
    speech_end: Optional[int] = None,
    music_start: int = 0,
    music_end: Optional[int] = None,
    speech_overlay_start: int = 0,
    music_overlay_start: int = 0,
    music_continue_after_speech: int = 5,
    fade_in_duration: int = 3,
    fade_out_duration: int = 3
):
    logger.info("Starting overlay request")
    logger.info(f"Received files: speech={speech_file.filename}, music={music_file.filename}")
    logger.info(f"Request headers: {request.headers}")
    logger.info(f"Speech file content type: {speech_file.content_type}")
    logger.info(f"Music file content type: {music_file.content_type}")
    
    speech_path = None
    music_path = None
    output_path = None
    
    try:
        # Validate file types
        for file in [speech_file, music_file]:
            if not file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.filename}. Supported types: mp3, wav, m4a, ogg"
                )
        
        # Save uploaded files asynchronously
        speech_path = await save_upload_file_async(speech_file)
        music_path = await save_upload_file_async(music_file)
        
        logger.info(f"Files saved: speech={speech_path}, music={music_path}")
        
        # Verify input files
        if not verify_audio(speech_path):
            raise HTTPException(status_code=400, detail="Speech file is invalid or empty")
        if not verify_audio(music_path):
            raise HTTPException(status_code=400, detail="Music file is invalid or empty")
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = os.path.join(OUTPUT_DIR, f"combined_audio_{timestamp}.mp3")
        
        logger.info(f"Processing audio files: {speech_path}, {music_path}")
        
        # Process audio
        overlay_audio(
            speech_path, music_path, output_path,
            music_volume_adjustment, speech_start, speech_end,
            music_start, music_end, speech_overlay_start,
            music_overlay_start, music_continue_after_speech,
            fade_in_duration, fade_out_duration
        )
        
        # Verify output file
        if not verify_audio(output_path):
            raise HTTPException(status_code=500, detail="Failed to generate valid output file")
            
        logger.info(f"Audio processing complete: {output_path}")
        
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Output file not found")
            
        # Get file size for logging
        file_size = os.path.getsize(output_path)
        logger.info(f"Output file size: {file_size} bytes")
        
        # Read the file into memory before cleanup
        async with aiofiles.open(output_path, 'rb') as f:
            content = await f.read()
            
        # Clean up all files
        cleanup_files(speech_path, music_path, output_path)
        
        logger.info("Sending response")
        
        # Check if the client accepts audio/mpeg
        accept_header = request.headers.get('accept', '')
        logger.info(f"Client accept header: {accept_header}")
        
        # Get user agent for debugging
        user_agent = request.headers.get('user-agent', '')
        logger.info(f"Client user agent: {user_agent}")
        
        # Check if the request is coming from n8n
        is_n8n = 'axios' in user_agent.lower()
        logger.info(f"Request is from n8n: {is_n8n}")
        
        # If it's n8n, return a JSON response with the audio as base64
if is_n8n:
    import base64
    audio_base64 = base64.b64encode(content).decode('utf-8')
    data_uri = f"data:audio/mpeg;base64,{audio_base64}"
    return JSONResponse(
        content={
            "filename": f"combined_audio_{timestamp}.mp3",
            "contentType": "audio/mpeg",
            "data": data_uri  # Now includes the data URI prefix
        }
    )      
        # For other clients, return the binary audio file
        return Response(
            content=content,
            media_type="audio/mpeg",
            headers={
                'Content-Disposition': f'attachment; filename="combined_audio_{timestamp}.mp3"',
                'Content-Length': str(len(content)),
                'Content-Type': 'audio/mpeg',
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        # Clean up any files if there was an error
        cleanup_files(speech_path, music_path, output_path)
        logger.error(f"Error in create_overlay: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def adjust_background_music(speech: AudioSegment, music: AudioSegment, music_volume_adjustment: int) -> AudioSegment:
    """
    Adjust the volume of background music relative to speech.
    
    Parameters:
    - speech: The speech AudioSegment
    - music: The music AudioSegment
    - music_volume_adjustment: Volume adjustment in dB
    
    Returns:
    - Adjusted music AudioSegment
    """
    logger.info(f"Adjusting music volume by {music_volume_adjustment} dB")
    return music + music_volume_adjustment

def apply_fades(audio: AudioSegment, fade_in_duration: int = 0, fade_out_duration: int = 0) -> AudioSegment:
    """
    Apply fade-in and fade-out effects to audio.
    
    Parameters:
    - audio: The AudioSegment to apply fades to
    - fade_in_duration: Duration of fade in (seconds)
    - fade_out_duration: Duration of fade out (seconds)
    
    Returns:
    - AudioSegment with fades applied
    """
    if fade_in_duration > 0:
        logger.info(f"Applying fade in: {fade_in_duration} seconds")
        audio = audio.fade_in(fade_in_duration * 1000)
    if fade_out_duration > 0:
        logger.info(f"Applying fade out: {fade_out_duration} seconds")
        audio = audio.fade_out(fade_out_duration * 1000)
    return audio

def overlay_audio(
    speech_path: str,
    music_path: str,
    output_path: str,
    music_volume_adjustment: int = -10,
    speech_start: int = 0,
    speech_end: Optional[int] = None,
    music_start: int = 0,
    music_end: Optional[int] = None,
    speech_overlay_start: int = 0,
    music_overlay_start: int = 0,
    music_continue_after_speech: int = 0,
    fade_in_duration: int = 0,
    fade_out_duration: int = 0
) -> None:
    """
    Overlay a speech/lyrics audio file with background music.
    
    Parameters:
    - speech_path: Path to speech audio file
    - music_path: Path to background music file
    - output_path: Path for output file
    - music_volume_adjustment: How many dB to adjust music volume
    - speech_start: Start time in speech file (seconds)
    - speech_end: End time in speech file (seconds)
    - music_start: Start time in music file (seconds)
    - music_end: End time in music file (seconds)
    - speech_overlay_start: When to start overlay in speech (seconds)
    - music_overlay_start: When to start overlay in music (seconds)
    - music_continue_after_speech: How long music continues after speech (seconds)
    - fade_in_duration: Duration of fade in effect (seconds)
    - fade_out_duration: Duration of fade out effect (seconds)
    """
    try:
        logger.info("Loading audio files")
        # Load audio files
        speech = AudioSegment.from_file(speech_path)
        music = AudioSegment.from_file(music_path)
        
        logger.info(f"Speech duration: {len(speech)}ms, Music duration: {len(music)}ms")
        
        # Extract portions of audio files
        speech = speech[speech_start * 1000:speech_end * 1000 if speech_end else len(speech)]
        music = music[music_start * 1000:music_end * 1000 if music_end else len(music)]
        
        logger.info(f"After trimming - Speech duration: {len(speech)}ms, Music duration: {len(music)}ms")
        
        # Adjust music volume
        adjusted_music = adjust_background_music(speech, music, music_volume_adjustment)
        
        # Create silence for padding
        silence = AudioSegment.silent(duration=speech_overlay_start * 1000)
        
        # Combine audio
        result = silence + speech
        
        # Overlay adjusted music starting at the specified position
        music_position = speech_overlay_start * 1000
        result = result.overlay(adjusted_music, position=music_position)
        
        # Add continuation of music after speech if specified
        if music_continue_after_speech > 0:
            logger.info(f"Adding {music_continue_after_speech} seconds of music continuation")
            result = result + adjusted_music[len(result) - music_position:len(result) - music_position + (music_continue_after_speech * 1000)]
        
        # Apply fades
        result = apply_fades(result, fade_in_duration, fade_out_duration)
        
        logger.info(f"Final audio duration: {len(result)}ms")
        
        # Export result
        logger.info(f"Exporting to {output_path}")
        result.export(output_path, format="mp3")
        
        # Verify the exported file
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"Export successful. File size: {file_size} bytes")
        else:
            raise Exception("Failed to create output file")
            
    except Exception as e:
        logger.error(f"Error in overlay_audio: {str(e)}")
        raise

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
