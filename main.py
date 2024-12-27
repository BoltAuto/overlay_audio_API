import os
import logging
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydub import AudioSegment
import uvicorn
from typing import Optional
import shutil

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

def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file and return the path"""
    try:
        # Create a unique filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{upload_file.filename}"
        temp_file_path = os.path.join(TEMP_DIR, filename)
        
        logger.info(f"Saving file to: {temp_file_path}")
        
        # Save the file using a buffer to handle large files
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        
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
    speech_path = None
    music_path = None
    output_path = None
    
    try:
        logger.info("Starting audio overlay process")
        
        # Validate file types
        for file in [speech_file, music_file]:
            if not file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.filename}. Supported types: mp3, wav, m4a, ogg"
                )
        
        # Save uploaded files
        speech_path = save_upload_file(speech_file)
        music_path = save_upload_file(music_file)
        
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
        with open(output_path, 'rb') as f:
            content = f.read()
            
        # Clean up all files
        cleanup_files(speech_path, music_path, output_path)
        
        # Return the file content directly
        return Response(
            content=content,
            media_type="audio/mpeg",
            headers={
                'Content-Disposition': f'attachment; filename="combined_audio_{timestamp}.mp3"',
                'Content-Length': str(len(content))
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
