import gradio as gr

from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip

import os
import openai
import subprocess
from pathlib import Path
import uuid
import tempfile
import shlex
import shutil

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY


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
            info["duration"] = str(video.duration) + "s"
            info["dimensions"] = "{}x{}".format(video.size[0], video.size[1])
            video.close()
        elif file_extension in (".mp3", ".wav"):
            info["type"] = "audio"
            audio = AudioFileClip(file.name)
            info["duration"] = str(audio.duration) + "s"
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


def get_completion(prompt, files_info):

    files_info_string = "".join(str(x) for x in files_info)
    messages = [
        {
            "role": "system",
            # "content": f"""Act as a FFMPEG expert. Create a valid FFMPEG command that will be directly pasted in the terminal. Using those files: {files_info} create the FFMPEG command to achieve this: "{prompt}". Make sure it's a valid command that will not do any error. Always name the output of the FFMPEG command "output.mp4". Always use the FFMPEG overwrite option (-y). Don't produce video longer than 1 minute. Think step by step but never give any explanation, only the shell command.""",
            # "content": f"""You'll need to create a valid FFMPEG command that will be directly pasted in the terminal. You have those files (images, videos, and audio) at your disposal: {files_info} and you need to compose a new video using FFMPEG and following those instructions: "{prompt}". You'll need to use as many assets as you can. Make sure it's a valid command that will not do any error. Always name the output of the FFMPEG command "output.mp4". Always use the FFMPEG overwrite option (-y). Try to avoid using -filter_complex option.  Don't produce video longer than 1 minute. Think step by step but never give any explanation, only the shell command.""",
            "content": f"""
You are a very experienced agent controlling a UNIX terminal and a contributor to the ffmpeg project. You are given:
(1) a set of video, audio and/or image assets. Including their name, duration, dimensions and file size
(2) the description of a new video you need to create from the list of assets

Based on the available assets and the description, your objective issue a FFMPEG to create a new video using the assets.

This will often involve putting assets one after the other, cropping the video format, or playing music in the background. Avoid using complex FFMPEG options, and try to keep the command as simple as possible as it will be directly paster into the terminal.
Always output the media a video/mp4 and output file "output.mp4". Provide only the shell command without any explanations.

The current assets and objective follow. Reply with the FFMPEG command:

AVAILABLE ASSETS LIST: {files_info_string}
OBJECTIVE: {prompt}
YOUR FFMPEG COMMAND:""",
        }
    ]

    print(messages)

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4", messages=messages)

        command = completion.choices[0].message.content.replace("\n", "")

        # remove output.mp4 with the actual output file path
        command = command.replace("output.mp4", "")

        return command
    except Exception as e:
        print("FROM OPENAI", e)
        raise Exception("OpenAI API error")


def update(files, prompt):
    if prompt == "":
        raise gr.Error("Please enter a prompt.")

    files_info = get_files_infos(files)

    try:
        command_string = get_completion(prompt, files_info)
        print(
            f"""\n\n/// START OF COMMAND ///:\n{command_string}\n/// END OF COMMAND ///\n\n""")

        # split command string into list of arguments
        args = shlex.split(command_string)
        if (args[0] != "ffmpeg"):
            raise Exception("Command does not start with ffmpeg")
        temp_dir = tempfile.mkdtemp()
        # copy files to temp dir
        for file in files:
            file_path = Path(file.name)
            shutil.copy(file_path, temp_dir)

        # test if ffmpeg command is valid dry run
        ffmpg_dry_run = subprocess.run(
            args + ["-f", "null", "-"], stderr=subprocess.PIPE, text=True, cwd=temp_dir)
        if ffmpg_dry_run.returncode == 0:
            print("Command is valid.")
        else:
            print("Command is not valid. Error output:")
            print(ffmpg_dry_run.stderr)
            raise Exception(
                "FFMPEG generated command is not valid. Please try again.")

        output_file_name = f'output_{uuid.uuid4()}.mp4'
        output_file_path = str((Path(temp_dir) / output_file_name).resolve())
        subprocess.run(args + ["-y", output_file_path], cwd=temp_dir)

        return output_file_path
    except Exception as e:
        print("FROM UPDATE", e)
        raise gr.Error(e)


css = """
# #header {
#     padding: 1.5rem 0 0.8rem;
# }
# #header h1 {
#     font-size: 1.5rem; margin-bottom: 0.3rem;
# }
# .boundedheight, .unpadded_box {
#     height: 30vh !important;
#     max-height: 50vh !important;
# }
"""

with gr.Blocks(css=css) as demo:
    gr.Markdown(
        """
            # <span style="margin-right: 0.3rem;">🏞</span> Video Composer
            Add video, image and audio assets and ask ChatGPT to compose a new video.
        """,
        elem_id="header",
    )
    with gr.Row():
        with gr.Column():
            user_files = gr.File(
                file_count="multiple", label="Media files", keep_filename=True
            )
            user_prompt = gr.Textbox(
                placeholder="I want to convert to a gif under 15mb",
                label="Instructions",
            )
            btn = gr.Button("Run", label="Run")
        with gr.Column():
            generated_video = gr.Video(
                interactive=False, label="Generated Video", include_audio=True
            )

        btn.click(
            fn=update, inputs=[user_files,
                               user_prompt], outputs=[generated_video]
        )
    with gr.Row():
        gr.Examples(
            examples=[
                [[
                    "./examples/cat8.jpeg",
                    "./examples/cat1.jpeg",
                    "./examples/cat2.jpeg",
                    "./examples/cat3.jpeg",
                    "./examples/cat4.jpeg",
                    "./examples/cat5.jpeg",
                    "./examples/cat6.jpeg",
                    "./examples/cat7.jpeg"],
                    "make a video gif given each image 1s loop"
                 ],
                [
                    ["./examples/example.mp4"],
                    "please encode this video 10 times faster"
                ],
                [
                    ["./examples/heat-wave.mp3", "./examples/square-image.png"],
                    "Make a 720x720 video with a white waveform of the audio taking all screen space, also add the image as the background",
                ],
                [
                    ["./examples/waterfall-overlay.png",
                        "./examples/waterfall.mp4"],
                    "Add the overlay to the video.",
                ],
            ],
            inputs=[user_files, user_prompt],
            outputs=generated_video,
            fn=update,
            cache_examples=True,
        )

    with gr.Row():

        gr.Markdown(
            """
            If you have idea to improve this please open a PR:

            [![Open a Pull Request](https://huggingface.co/datasets/huggingface/badges/raw/main/open-a-pr-lg-light.svg)](https://huggingface.co/spaces/victor/ChatUI/discussions)
            """,
        )

demo.launch()
