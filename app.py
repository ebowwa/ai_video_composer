# NEED: 
# - have gemini watch beforehand then send to deepseek-ai/DeepSeek-V3
# - gemini should respond with the video description and best ffmpeg options to use with the available content;

import gradio as gr

from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip
import openai
import os
from pathlib import Path
import uuid
import tempfile
import shlex
import shutil
from dotenv import load_dotenv
import subprocess

# Load environment variables from .env file
load_dotenv()

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file")

SITE_URL = os.getenv("SITE_URL", "http://localhost:7860")
APP_NAME = os.getenv("APP_NAME", "AI-Video-Composer")

allowed_medias = [
    ".png",
    ".jpg",
    ".webp",
    ".jpeg",
    ".tiff",
    ".bmp",
    ".gif",
    ".svg",
    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".flv",
    ".wmv",
    ".webm",
    ".mpg",
    ".mpeg",
    ".m4v",
    ".3gp",
    ".3g2",
    ".3gpp",
]


def get_files_infos(files):
    """Get information about uploaded files."""
    files_info = []
    for file in files:
        file_info = {}
        file_info["name"] = file.name
        file_info["type"] = None
        
        # Get file extension
        _, ext = os.path.splitext(file.name)
        ext = ext.lower()
        
        try:
            if ext in [".wav", ".mp3", ".m4a", ".aac"]:
                audio = AudioFileClip(file.name)
                file_info["type"] = "audio"
                file_info["duration"] = audio.duration
                audio.close()
            elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
                try:
                    with Image.open(file.name) as img:
                        width, height = img.size
                        file_info["type"] = "image"
                        file_info["dimensions"] = f"{width}x{height}"
                except Exception as e:
                    print(f"Error processing image {file.name}: {str(e)}")
                    continue
            elif ext in [".mp4", ".mov", ".avi", ".mkv"]:
                video = VideoFileClip(file.name)
                file_info["type"] = "video"
                file_info["duration"] = video.duration
                file_info["dimensions"] = f"{video.size[0]}x{video.size[1]}"
                video.close()
        except Exception as e:
            print(f"Error processing file {file.name}: {str(e)}")
            continue
            
        if file_info["type"]:
            files_info.append(file_info)
    
    return files_info


def get_completion(prompt, files_info, top_p=1, temperature=1, model_choice="deepseek/deepseek-chat"):
    """Generate FFMPEG command locally"""
    try:
        # Get audio and image files
        audio_files = [f for f in files_info if f["type"] == "audio"]
        image_files = [f for f in files_info if f["type"] == "image"]
        
        if not audio_files:
            raise ValueError("No audio files found")
        if not image_files:
            raise ValueError("No image files found")
        
        # Use the first audio and image file
        audio_file = audio_files[0]["name"]
        image_file = image_files[0]["name"]
        
        # Build FFmpeg command for waveform visualization
        command = f'ffmpeg -i "{audio_file}" -i "{image_file}" -filter_complex "[0:a]aformat=channel_layouts=mono,showwaves=s=1024x200:mode=line:colors=white[wave];[1:v][wave]overlay=(W-w)/2:(H-h)/2:format=auto,format=yuv420p" -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k output.mp4'
        
        return command

    except Exception as e:
        print(f"Error generating command: {str(e)}")
        return None


def update(
    files,
    prompt,
    top_p=1,
    temperature=1,
    model_choice="deepseek/deepseek-chat",
):
    if not files:
        raise gr.Error("Please upload at least one media file.")
    if prompt == "":
        raise gr.Error("Please enter a prompt.")

    try:
        files_info = get_files_infos(files)
        if not files_info:
            raise gr.Error("No valid media files were found. Please check the uploaded files.")

        try:
            command_string = get_completion(
                prompt, files_info, top_p, temperature, model_choice
            )
            
            if not command_string:
                raise gr.Error("Failed to generate FFMPEG command. Please try again.")

            # Create a temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy files to temp directory with sanitized names
                for file, info in zip(files, files_info):
                    temp_path = os.path.join(temp_dir, os.path.basename(info["name"]))
                    shutil.copy2(file.name, temp_path)

                # Execute the command
                try:
                    # Run the command in the temporary directory
                    process = subprocess.Popen(
                        shlex.split(command_string),
                        cwd=temp_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()

                    if process.returncode != 0:
                        print(f"FFMPEG Error: {stderr}")
                        raise gr.Error(f"FFMPEG Error: {stderr}")

                    # Copy output file to current directory
                    output_path = os.path.join(temp_dir, "output.mp4")
                    if os.path.exists(output_path):
                        shutil.copy2(output_path, "output.mp4")
                        return "output.mp4", "Video generated successfully! 🎉"
                    else:
                        raise gr.Error("Output file was not generated")

                except subprocess.SubprocessError as e:
                    print(f"Command execution failed: {str(e)}")
                    raise gr.Error(f"Command execution failed: {str(e)}")

        except Exception as e:
            print(f"Error: {str(e)}")
            raise gr.Error(str(e))

    except Exception as e:
        print(f"Error: {str(e)}")
        raise gr.Error(str(e))

    return None, "Failed to generate video"


with gr.Blocks() as demo:
    gr.Markdown(
        """
            # 🏞 AI Video Composer
            Compose new videos from your assets using natural language. Add video, image and audio assets and let [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) or [DeepSeek-V3](https://huggingface.co/deepseek-ai/DeepSeek-V3-Base) generate a new video for you (using FFMPEG).
        """,
        elem_id="header",
    )
    with gr.Row():
        with gr.Column():
            user_files = gr.File(
                file_count="multiple",
                label="Media files",
                file_types=allowed_medias,
            )
            user_prompt = gr.Textbox(
                placeholder="eg: Remove the 3 first seconds of the video",
                label="Instructions",
            )
            btn = gr.Button("Run")
            with gr.Accordion("Parameters", open=False):
                model_choice = gr.Dropdown(
                    choices=[
                        "deepseek/deepseek-chat",
                        "anthropic/claude-3-opus",
                        "meta-llama/llama-2-70b-chat",
                        "google/gemini-pro",
                    ],
                    value="deepseek/deepseek-chat",
                    label="Model",
                )
                top_p = gr.Slider(
                    minimum=-0,
                    maximum=1.0,
                    value=0.7,
                    step=0.05,
                    interactive=True,
                    label="Top-p (nucleus sampling)",
                )
                temperature = gr.Slider(
                    minimum=-0,
                    maximum=5.0,
                    value=0.1,
                    step=0.1,
                    interactive=True,
                    label="Temperature",
                )
        with gr.Column():
            generated_video = gr.Video(
                interactive=False, label="Generated Video", include_audio=True
            )
            generated_command = gr.Markdown()

        btn.click(
            fn=update,
            inputs=[user_files, user_prompt, top_p, temperature, model_choice],
            outputs=[generated_video, generated_command],
        )
    with gr.Row():
        gr.Examples(
            examples=[
                [
                    ["./examples/ai_talk.wav", "./examples/bg-image.png"],
                    "Use the image as the background with a waveform visualization for the audio positioned in center of the video.",
                    0.7,
                    0.1,
                    "deepseek/deepseek-chat",
                ],
                [
                    ["./examples/ai_talk.wav", "./examples/bg-image.png"],
                    "Use the image as the background with a waveform visualization for the audio positioned in center of the video. Make sure the waveform has a max height of 250 pixels.",
                    0.7,
                    0.1,
                    "deepseek/deepseek-chat",
                ],
                [
                    [
                        "./examples/cat1.jpeg",
                        "./examples/cat2.jpeg",
                        "./examples/cat3.jpeg",
                        "./examples/cat4.jpeg",
                        "./examples/cat5.jpeg",
                        "./examples/cat6.jpeg",
                        "./examples/heat-wave.mp3",
                    ],
                    "Create a 3x2 grid of the cat images with the audio as background music. Make the video duration match the audio duration.",
                    0.7,
                    0.1,
                    "deepseek/deepseek-chat",
                ],
            ],
            inputs=[user_files, user_prompt, top_p, temperature, model_choice],
            outputs=[generated_video, generated_command],
            fn=update,
            run_on_click=True,
            cache_examples=False,
        )

    with gr.Row():
        gr.Markdown(
            """
            If you have idea to improve this please open a PR:

            [![Open a Pull Request](https://huggingface.co/datasets/huggingface/badges/raw/main/open-a-pr-lg-light.svg)](https://huggingface.co/spaces/huggingface-projects/video-composer-gpt4/discussions)
            """,
        )

demo.queue(default_concurrency_limit=200)
demo.launch(show_api=False)
