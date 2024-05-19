import os
from pydub import AudioSegment
from datetime import datetime

def adjust_background_music(speech, music, music_volume_adjustment):
    """
    Adjusts the volume of the background music to ensure it doesn't overpower the speech.
    """
    # Normalize speech
    speech = speech.normalize()

    # Set the background music to a relative volume lower than the speech
    music = music.apply_gain(music_volume_adjustment)
    
    return speech, music

def apply_fades(audio, fade_in_duration=0, fade_out_duration=0):
    """
    Applies fade-in and fade-out effects to the audio.
    """
    if fade_in_duration > 0:
        audio = audio.fade_in(fade_in_duration * 1000)
    if fade_out_duration > 0:
        audio = audio.fade_out(fade_out_duration * 1000)
    return audio

def overlay_audio(speech_path, music_path, output_path, music_volume_adjustment=-10, 
                  speech_start=0, speech_end=None, music_start=0, music_end=None, 
                  speech_overlay_start=0, music_overlay_start=0, music_continue_after_speech=0,
                  fade_in_duration=0, fade_out_duration=0):
    """
    Overlays a speech/lyrics audio file with background music.
    """
    # Load audio files
    speech = AudioSegment.from_file(speech_path)
    music = AudioSegment.from_file(music_path)
    
    # Trim speech and music files
    speech = speech[speech_start*1000:speech_end*1000 if speech_end else len(speech)]
    music = music[music_start*1000:music_end*1000 if music_end else len(music)]
    
    # Adjust background music volume
    speech, music = adjust_background_music(speech, music, music_volume_adjustment)

    # Pad the start of the music and speech with silence if overlay_start is specified
    if music_overlay_start > 0:
        music = AudioSegment.silent(duration=music_overlay_start*1000) + music
    if speech_overlay_start > 0:
        speech = AudioSegment.silent(duration=speech_overlay_start*1000) + speech
    
    # Ensure music is at least as long as the speech, adding silence if necessary
    if len(music) < len(speech):
        music = (music * (len(speech) // len(music) + 1))[:len(speech)]
    if len(music) < len(speech):
        music = music + AudioSegment.silent(duration=len(speech) - len(music))
    
    # Apply fades
    combined_duration = len(speech) + music_continue_after_speech * 1000
    combined = music.overlay(speech, position=speech_overlay_start * 1000)
    combined = combined[:combined_duration]
    combined = apply_fades(combined, fade_in_duration, fade_out_duration)
    
    # Export the final audio
    combined.export(output_path, format="mp3")

def main():
    # Define input paths
    speech_path = "path/to/speech.mp3"
    music_path = "path/to/music.mp3"
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Define output dir
    output_dir = "output_audio"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate the output path
    output_path = os.path.join(output_dir, f"combined_audio_{current_time}.mp3")
    
    # Parameters for overlay
    music_volume_adjustment = -10  # Music will be 10 dB quieter than speech
    speech_start = 0  # Start of the speech portion to use (in seconds)
    speech_end = None  # End of the speech portion to use (in seconds), None for full length
    music_start = 0  # Start of the music portion to use (in seconds)
    music_end = None  # End of the music portion to use (in seconds), None for full length
    speech_overlay_start = 0  # When to start the overlay in the speech file (in seconds)
    music_overlay_start = 0  # When to start the overlay in the music file (in seconds)
    music_continue_after_speech = 5  # How long the music continues after the speech ends (in seconds)
    fade_in_duration = 3  # Fade-in duration (in seconds)
    fade_out_duration = 3  # Fade-out duration (in seconds)
    
    # Overlay the audio
    overlay_audio(speech_path, music_path, output_path, music_volume_adjustment, 
                  speech_start, speech_end, music_start, music_end, 
                  speech_overlay_start, music_overlay_start, 
                  music_continue_after_speech, fade_in_duration, fade_out_duration)

if __name__ == "__main__":
    main()
