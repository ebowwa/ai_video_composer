import gradio as gr

from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip

import os
from openai import OpenAI
import subprocess
from pathlib import Path
import uuid
import tempfile
import shlex
import shutil

HF_API_KEY = os.environ["HF_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]

client = OpenAI(base_url="https://api-inference.huggingface.co/v1/", api_key=HF_API_KEY)

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
    results = []
    for file in files:
        file_path = Path(file.name)
        info = {}
        info["size"] = os.path.getsize(file_path)
        # Sanitize filename by replacing spaces with underscores
        info["name"] = file_path.name.replace(" ", "_")
        file_extension = file_path.suffix

        if file_extension in (".mp4", ".avi", ".mkv", ".mov"):
            info["type"] = "video"
            video = VideoFileClip(file.name)
            info["duration"] = video.duration
            info["dimensions"] = "{}x{}".format(video.size[0], video.size[1])
            if video.audio:
                info["type"] = "video/audio"
                info["audio_channels"] = video.audio.nchannels
            video.close()
        elif file_extension in (".mp3", ".wav"):
            info["type"] = "audio"
            audio = AudioFileClip(file.name)
            info["duration"] = audio.duration
            info["audio_channels"] = audio.nchannels
            audio.close()
        elif file_extension in (
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".bmp",
            ".gif",
            ".svg",
        ):
            info["type"] = "image"
            img = Image.open(file.name)
            info["dimensions"] = "{}x{}".format(img.size[0], img.size[1])
        results.append(info)
    return results


def get_completion(prompt, files_info, top_p, temperature, model_choice):
    # Create table header
    files_info_string = "| Type | Name | Dimensions | Duration | Audio Channels |\n"
    files_info_string += "|------|------|------------|-----------|--------|\n"

    # Add each file as a table row
    for file_info in files_info:
        dimensions = file_info.get("dimensions", "-")
        duration = (
            f"{file_info.get('duration', '-')}s" if "duration" in file_info else "-"
        )
        audio = (
            f"{file_info.get('audio_channels', '-')} channels"
            if "audio_channels" in file_info
            else "-"
        )

        files_info_string += f"| {file_info['type']} | {file_info['name']} | {dimensions} | {duration} | {audio} |\n"

    messages = [
        {
            "role": "system",
            "content": """
You are a very experienced media engineer, controlling a UNIX terminal.
You are an FFMPEG expert with years of experience and multiple contributions to the FFMPEG project.

You are given:
(1) a set of video, audio and/or image assets. Including their name, duration, dimensions and file size
(2) the description of a new video you need to create from the list of assets

Your objective is to generate the SIMPLEST POSSIBLE single ffmpeg command to create the requested video.

Key requirements:
    - Use the absolute minimum number of ffmpeg options needed
    - Avoid complex filter chains or filter_complex if possible
    - Prefer simple concatenation, scaling, and basic filters
    - Output exactly ONE command that will be directly pasted into the terminal
    - Never output multiple commands chained together
    - Output the command in a single line (no line breaks or multiple lines)
    - If the user asks for waveform visualization make sure to set the mode to `line` with and the use the full width of the video. Also concatenate the audio into a single channel.
    - For image sequences: Use -framerate and pattern matching (like 'img%d.jpg') when possible, falling back to individual image processing with -loop 1 and appropriate filters only when necessary.
    - When showing file operations or commands, always use explicit paths and filenames without wildcards - avoid using asterisk (*) or glob patterns. Instead, use specific numbered sequences (like %d), explicit file lists, or show the full filename.

Remember: Simpler is better. Only use advanced ffmpeg features if absolutely necessary for the requested output.
""",
        },
        {
            "role": "user",
            "content": f"""Always output the media as video/mp4 and output file with "output.mp4". Provide only the shell command without any explanations.
The current assets and objective follow. Reply with the FFMPEG command:

AVAILABLE ASSETS LIST:

{files_info_string}

OBJECTIVE: {prompt} and output at "output.mp4"
YOUR FFMPEG COMMAND:
         """,
        },
    ]
    try:
        # Print the complete prompt
        print("\n=== COMPLETE PROMPT ===")
        for msg in messages:
            print(f"\n[{msg['role'].upper()}]:")
            print(msg["content"])
        print("=====================\n")

        if model_choice == "deepseek-ai/DeepSeek-V3":
            client.base_url = "https://api.deepseek.com/v1"
            client.api_key = DEEPSEEK_API_KEY
            model = "deepseek-chat"
        else:
            client.base_url = "https://api-inference.huggingface.co/v1/"
            client.api_key = HF_API_KEY
            model = "Qwen/Qwen2.5-Coder-32B-Instruct"

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=2048,
        )
        content = completion.choices[0].message.content
        # Extract command from code block if present
        if "```" in content:
            # Find content between ```sh or ```bash and the next ```
            import re

            command = re.search(r"```(?:sh|bash)?\n(.*?)\n```", content, re.DOTALL)
            if command:
                command = command.group(1).strip()
            else:
                command = content.replace("\n", "")
        else:
            command = content.replace("\n", "")

        # remove output.mp4 with the actual output file path
        command = command.replace("output.mp4", "")

        return command
    except Exception as e:
        raise Exception("API Error")


def update(
    files,
    prompt,
    top_p=1,
    temperature=1,
    model_choice="Qwen/Qwen2.5-Coder-32B-Instruct",
):
    if prompt == "":
        raise gr.Error("Please enter a prompt.")

    files_info = get_files_infos(files)
    # disable this if you're running the app locally or on your own server
    for file_info in files_info:
        if file_info["type"] == "video":
            if file_info["duration"] > 120:
                raise gr.Error(
                    "Please make sure all videos are less than 2 minute long."
                )
        if file_info["size"] > 10000000:
            raise gr.Error("Please make sure all files are less than 10MB in size.")

    attempts = 0
    while attempts < 2:
        print("ATTEMPT", attempts)
        try:
            command_string = get_completion(
                prompt, files_info, top_p, temperature, model_choice
            )
            print(
                f"""///PROMTP {prompt} \n\n/// START OF COMMAND ///:\n\n{command_string}\n\n/// END OF COMMAND ///\n\n"""
            )

            # split command string into list of arguments
            args = shlex.split(command_string)
            if args[0] != "ffmpeg":
                raise Exception("Command does not start with ffmpeg")
            temp_dir = tempfile.mkdtemp()
            # copy files to temp dir with sanitized names
            for file in files:
                file_path = Path(file.name)
                sanitized_name = file_path.name.replace(" ", "_")
                shutil.copy(file_path, Path(temp_dir) / sanitized_name)

            # test if ffmpeg command is valid dry run
            ffmpg_dry_run = subprocess.run(
                args + ["-f", "null", "-"],
                stderr=subprocess.PIPE,
                text=True,
                cwd=temp_dir,
            )
            if ffmpg_dry_run.returncode == 0:
                print("Command is valid.")
            else:
                print("Command is not valid. Error output:")
                print(ffmpg_dry_run.stderr)
                raise Exception(
                    "FFMPEG generated command is not valid. Please try something else."
                )

            output_file_name = f"output_{uuid.uuid4()}.mp4"
            output_file_path = str((Path(temp_dir) / output_file_name).resolve())
            final_command = args + ["-y", output_file_path]
            print(
                f"\n=== EXECUTING FFMPEG COMMAND ===\nffmpeg {' '.join(final_command[1:])}\n"
            )
            subprocess.run(final_command, cwd=temp_dir)
            generated_command = f"### Generated Command\n```bash\nffmpeg {' '.join(args[1:])} -y output.mp4\n```"
            return output_file_path, gr.update(value=generated_command)
        except Exception as e:
            attempts += 1
            if attempts >= 2:
                print("FROM UPDATE", e)
                raise gr.Error(e)


with gr.Blocks() as demo:
    gr.Markdown(
        """
            # 🏞 AI Video Composer
            Compose new videos from your assets using natural language. Add video, image and audio assets and let [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) generate a new video for you (using FFMPEG).
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
                model_choice = gr.Radio(
                    choices=[
                        "Qwen/Qwen2.5-Coder-32B-Instruct",
                        "deepseek-ai/DeepSeek-V3",
                    ],
                    value="deepseek-ai/DeepSeek-V3",
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
                    "Qwen/Qwen2.5-Coder-32B-Instruct",
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
                    "deepseek-ai/DeepSeek-V3",
                ],
                [
                    [
                        "./examples/cat1.jpeg",
                        "./examples/cat2.jpeg",
                        "./examples/cat3.jpeg",
                        "./examples/cat4.jpeg",
                        "./examples/cat5.jpeg",
                        "./examples/cat6.jpeg",
                    ],
                    "Create a slideshow where each image is shown for 2 seconds with a continuous slight zoom effect.",
                    0.7,
                    0.1,
                    "deepseek-ai/DeepSeek-V3",
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
demo.launch(show_api=False, ssr_mode=False)
