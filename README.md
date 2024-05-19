## README.md

# Audio Overlay Script

This Python script overlays a speech/lyrics audio file with a background music file, ensuring the background music doesn't overpower the speech. The script uses `pydub` for audio manipulation and requires `ffmpeg` for processing audio files.

## Features

- Overlays a speech/lyrics audio file with background music.
- Allows specifying how much quieter the music should be compared to the speech.
- Allows selecting specific parts of both the speech and music files for the overlay.
- Ensures the music does not overpower the speech by adjusting the volume of the music.
- Supports padding with silence if the music is shorter than the speech.
- Allows specifying the start time for overlaying the music within the speech file.
- Generates a uniquely named output file using the current date and time to avoid conflicts.

## Requirements

- Python 3.6 or higher
- pydub
- ffmpeg

## Installation

1. Install `pydub` using pip:

   ```sh
   pip install pydub
   ```

2. Install `ffmpeg` and ensure it is added to your system's PATH. Follow the installation instructions from the [FFmpeg website](https://ffmpeg.org/download.html).

## Usage

1. Clone or download the repository.

2. Modify the `main()` function in the script to set the correct input paths, output directory, and overlay parameters.

3. Run the script:

   ```sh
   python audio_overlay.py
   ```

### Example Configuration

```python
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
    overlay_start = 0  # When to start the overlay in the speech file (in seconds)
    
    # Overlay the audio
    overlay_audio(speech_path, music_path, output_path, music_volume_adjustment, 
                  speech_start, speech_end, music_start, music_end, overlay_start)

if __name__ == "__main__":
    main()
```

## Functions

- `adjust_background_music(speech, music, music_volume_adjustment)`: Adjusts the volume of the background music to ensure it doesn't overpower the speech.
- `overlay_audio(speech_path, music_path, output_path, music_volume_adjustment=-10, 
                  speech_start=0, speech_end=None, music_start=0, music_end=None, 
                  overlay_start=0)`: Overlays a speech/lyrics audio file with background music.
- `main()`: Sets the input paths, output directory, and overlay parameters, and calls the `overlay_audio` function.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

### Notes

- Ensure `ffmpeg` is installed and accessible via the system's PATH.
- Adjust the `speech_path`, `music_path`, `output_dir`, and other parameters as necessary.
- The script generates a uniquely named output file based on the current date and time to avoid file name conflicts.