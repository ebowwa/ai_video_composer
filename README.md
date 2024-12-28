---
title: AI Video Composer
short_description: Create videos with FFMPEG + Qwen2.5-Coder
emoji: 🏞
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 5.6.0
app_file: app.py
pinned: false
disable_embedding: true
models:
  - Qwen/Qwen2.5-Coder-32B-Instruct
---

# 🏞 AI Video Composer

AI Video Composer is an intelligent media processing application that uses natural language instructions to create videos from your media assets. It leverages the Qwen2.5-Coder language model to generate FFmpeg commands based on your requirements.

## How It Works

1. **Upload Media Files**:

   - Supports multiple file formats including:
     - Images: .png, .jpg, .jpeg, .tiff, .bmp, .gif, .svg
     - Audio: .mp3, .wav, .ogg
     - Video: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, and more
   - File size limit: 10MB per file
   - Video duration limit: 2 minutes

2. **Provide Instructions**:

   - Write natural language instructions describing how you want to process your media
   - Examples:
     - "Convert these images into a slideshow with 1 second per image"
     - "Add this audio track to the video"
     - "Make the video play 2x faster"
     - "Create a waveform visualization for this audio file"

3. **Advanced Parameters**:

   - Top-p (nucleus sampling): Controls diversity of generated commands (0-1)
   - Temperature: Controls randomness in command generation (0-5)

4. **Processing**:
   - The app analyzes your files and instructions
   - Generates an optimized FFmpeg command using Qwen2.5-Coder
   - Executes the command and returns the processed video
   - Displays the generated FFmpeg command for transparency

## Features

- **Smart Command Generation**: Automatically generates optimal FFmpeg commands based on natural language input
- **Error Handling**: Validates commands before execution and retries with alternative approaches if needed
- **Multiple Asset Support**: Process multiple media files in a single operation
- **Waveform Visualization**: Special support for audio visualization with customizable parameters
- **Image Sequence Processing**: Efficient handling of image sequences for slideshow creation
- **Format Conversion**: Support for various input/output format conversions
- **Example Gallery**: Built-in examples demonstrating common use cases

## Technical Details

- Built with Gradio for the user interface
- Uses FFmpeg for media processing
- Powered by Qwen2.5-Coder for command generation
- Implements robust error handling and command validation
- Processes files in a temporary directory for safety
- Supports both simple operations and complex media transformations

## Limitations

- Maximum file size: 10MB per file
- Maximum video duration: 2 minutes
- Output format: Always MP4
- Processing time may vary based on input complexity

## Contributing

If you have ideas for improvements or bug fixes, please open a PR:

[![Open a Pull Request](https://huggingface.co/datasets/huggingface/badges/raw/main/open-a-pr-lg-light.svg)](https://huggingface.co/spaces/huggingface-projects/video-composer-gpt4/discussions)
# ai_video_composer
