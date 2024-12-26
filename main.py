import os
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydub import AudioSegment
import uvicorn
from typing import Optional

app = FastAPI(title="Audio Overlay API")

# Create temporary directory for file processing
os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file and return the path"""
    temp_file_path = f"temp/{upload_file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(upload_file.file.read())
    return temp_file_path

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
    """
    Create an audio overlay from two files.
    
    Parameters:
    - speech_file: Main audio file (vocals/speech)
    - music_file: Background music file
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
        # Save uploaded files
        speech_path = save_upload_file(speech_file)
        music_path = save_upload_file(music_file)
        
        # Generate output filename
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = f"output/combined_audio_{current_time}.mp3"
        
        # Process audio
        overlay_audio(
            speech_path, music_path, output_path,
            music_volume_adjustment, speech_start, speech_end,
            music_start, music_end, speech_overlay_start,
            music_overlay_start, music_continue_after_speech,
            fade_in_duration, fade_out_duration
        )
        
        # Clean up temporary files
        os.remove(speech_path)
        os.remove(music_path)
        
        # Return the processed file
        return FileResponse(
            output_path, 
            filename=f"combined_audio_{current_time}.mp3",
            media_type="audio/mpeg"
        )
    
    except Exception as e:
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
        audio = audio.fade_in(fade_in_duration * 1000)
    if fade_out_duration > 0:
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
    # Load audio files
    speech = AudioSegment.from_file(speech_path)
    music = AudioSegment.from_file(music_path)
    
    # Extract portions of audio files
    speech = speech[speech_start * 1000:speech_end * 1000 if speech_end else len(speech)]
    music = music[music_start * 1000:music_end * 1000 if music_end else len(music)]
    
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
        result = result + adjusted_music[len(result) - music_position:len(result) - music_position + (music_continue_after_speech * 1000)]
    
    # Apply fades
    result = apply_fades(result, fade_in_duration, fade_out_duration)
    
    # Export result
    result.export(output_path, format="mp3")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))  # Changed default to 8080
    uvicorn.run(app, host="0.0.0.0", port=port)
