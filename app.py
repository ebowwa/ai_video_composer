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
from utils import format_bash_command

HF_API_KEY = os.environ["HF_TOKEN"]

client = OpenAI(
    base_url="https://api-inference.huggingface.co/v1/",
    api_key=HF_API_KEY
)

allowed_medias = [
    ".png",
    ".jpg",
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
        info["name"] = file_path.name
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


def get_completion(prompt, files_info, top_p, temperature):
    files_info_string = ""
    for file_info in files_info:
        files_info_string += f"""{file_info["type"]} {file_info["name"]}"""
        if file_info["type"] == "video" or file_info["type"] == "image":
            files_info_string += f""" {file_info["dimensions"]}"""
        if file_info["type"] == "video" or file_info["type"] == "audio":
            files_info_string += f""" {file_info["duration"]}s"""
        if file_info["type"] == "audio" or file_info["type"] == "video/audio":
            files_info_string += f""" {file_info["audio_channels"]} audio channels"""
        files_info_string += "\n"

    messages = [
        {
            "role": "system",
            # "content": f"""Act as a FFMPEG expert. Create a valid FFMPEG command that will be directly pasted in the terminal. Using those files: {files_info} create the FFMPEG command to achieve this: "{prompt}". Make sure it's a valid command that will not do any error. Always name the output of the FFMPEG command "output.mp4". Always use the FFMPEG overwrite option (-y). Don't produce video longer than 1 minute. Think step by step but never give any explanation, only the shell command.""",
            # "content": f"""You'll need to create a valid FFMPEG command that will be directly pasted in the terminal. You have those files (images, videos, and audio) at your disposal: {files_info} and you need to compose a new video using FFMPEG and following those instructions: "{prompt}". You'll need to use as many assets as you can. Make sure it's a valid command that will not do any error. Always name the output of the FFMPEG command "output.mp4". Always use the FFMPEG overwrite option (-y). Try to avoid using -filter_complex option.  Don't produce video longer than 1 minute. Think step by step but never give any explanation, only the shell command.""",
            "content": """
You are a very experienced media engineer, controlling a UNIX terminal.
You are an FFMPEG expert with years of experience and multiple contributions to the FFMPEG project.

You are given:
(1) a set of video, audio and/or image assets. Including their name, duration, dimensions and file size
(2) the description of a new video you need to create from the list of assets

Based on the available assets and the description, your objective is to issue a SINGLE FFMPEG command to create a new video using the assets.
This will often involve putting assets one after the other, cropping the video format, or playing music in the background. Avoid using complex FFMPEG options, and try to keep the command as simple as possible as it will be directly pasted into the terminal.

IMPORTANT: Always output exactly ONE ffmpeg command, never multiple commands chained together.
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
        completion = client.chat.completions.create(
            model="Qwen/Qwen2.5-Coder-32B-Instruct",
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=2048
        )
        content = completion.choices[0].message.content
        # Extract command from code block if present
        if "```" in content:
            # Find content between ```sh or ```bash and the next ```
            import re
            command = re.search(r'```(?:sh|bash)?\n(.*?)\n```', content, re.DOTALL)
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
        print("FROM OPENAI", e)
        raise Exception("OpenAI API error")


def update(files, prompt, top_p=1, temperature=1):
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
            command_string = get_completion(prompt, files_info, top_p, temperature)
            print(
                f"""///PROMTP {prompt} \n\n/// START OF COMMAND ///:\n\n{command_string}\n\n/// END OF COMMAND ///\n\n"""
            )

            # split command string into list of arguments
            args = shlex.split(command_string)
            if args[0] != "ffmpeg":
                raise Exception("Command does not start with ffmpeg")
            temp_dir = tempfile.mkdtemp()
            # copy files to temp dir
            for file in files:
                file_path = Path(file.name)
                shutil.copy(file_path, temp_dir)

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
                    "FFMPEG generated command is not valid. Please try again."
                )

            output_file_name = f"output_{uuid.uuid4()}.mp4"
            output_file_path = str((Path(temp_dir) / output_file_name).resolve())
            subprocess.run(args + ["-y", output_file_path], cwd=temp_dir)
            generated_command = f"### Generated Command\n```bash\n{format_bash_command(args)}\n    -y output.mp4\n```"
            return output_file_path, gr.update(value=generated_command)
        except Exception as e:
            attempts += 1
            if attempts >= 2:
                print("FROM UPDATE", e)
                raise gr.Error(e)


with gr.Blocks() as demo:
    gr.Markdown(
        """
            # 🏞 Video Composer
            Add video, image and audio assets and let Qwen2.5-Coder compose a new video.
            **Please note: This demo is not a generative AI model, it only uses Qwen2.5-Coder to generate a valid FFMPEG command based on the input files and the prompt.**
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
                placeholder="I want to convert to a gif under 15mb",
                label="Instructions",
            )
            btn = gr.Button("Run")
            with gr.Accordion("Parameters", open=False):
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
                    value=0.5,
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
            inputs=[user_files, user_prompt, top_p, temperature],
            outputs=[generated_video, generated_command],
        )
    with gr.Row():
        gr.Examples(
            examples=[
                [
                    [
                        "./examples/cat8.jpeg",
                        "./examples/cat1.jpeg",
                        "./examples/cat2.jpeg",
                        "./examples/cat3.jpeg",
                        "./examples/cat4.jpeg",
                        "./examples/cat5.jpeg",
                        "./examples/cat6.jpeg",
                        "./examples/cat7.jpeg",
                        "./examples/heat-wave.mp3",
                    ],
                    "make a video gif, each image with 1s loop and add the audio as background",
                    0,
                    0,
                ],
                [
                    ["./examples/example.mp4"],
                    "please encode this video 10 times faster",
                    0,
                    0,
                ],
                [
                    ["./examples/heat-wave.mp3", "./examples/square-image.png"],
                    "Make a 720x720 video, a white waveform of the audio, and finally add add the input image as the background all along the video.",
                    0,
                    0,
                ],
                [
                    ["./examples/waterfall-overlay.png", "./examples/waterfall.mp4"],
                    "Add the overlay to the video.",
                    0,
                    0,
                ],
            ],
            inputs=[user_files, user_prompt, top_p, temperature],
            outputs=[generated_video, generated_command],
            fn=update,
            run_on_click=True,
            cache_examples=True,
        )

    with gr.Row():
        gr.Markdown(
            """
            If you have idea to improve this please open a PR:

            [![Open a Pull Request](https://huggingface.co/datasets/huggingface/badges/raw/main/open-a-pr-lg-light.svg)](https://huggingface.co/spaces/huggingface-projects/video-composer-gpt4/discussions)
            """,
        )
demo.queue(api_open=False)
demo.launch(show_api=False)
