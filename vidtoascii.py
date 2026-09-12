#!/usr/bin/env python3
import cv2
import time
import sys
import os
import requests
import numpy as np
from urllib.parse import urlparse
import subprocess

ASCII_CHARS = [" ", ".", ":", "-", "=", "+", "*", "%", "@", "#"]

def frame_to_ascii(frame, new_width=128, brightness=1.0):
    # 1. Increase color saturation to make terminal colors vibrant
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = np.clip(s * 1.5, 0, 255).astype(np.uint8)
    vibrant_frame = cv2.merge([h, s, v])
    color_frame = cv2.cvtColor(vibrant_frame, cv2.COLOR_HSV2BGR)
    
    h_orig, w_orig, _ = color_frame.shape
    # Ratio 0.43 keeps pixels square since terminal characters are taller than wide
    new_height = int((h_orig / w_orig) * new_width * 0.43)
    
    resized_color = cv2.resize(color_frame, (new_width, new_height))
    
    if brightness != 1.0:
        resized_color = np.clip(resized_color * brightness, 0, 255).astype(np.uint8)
    
    ascii_list = []
    CHAR = "█"
    
    for r in range(new_height):
        for c in range(new_width):
            b, g, r_val = resized_color[r, c]
            # Color both text foreground (38) and background (48) for a solid pixel block
            ascii_list.append(f"\033[38;2;{r_val};{g};{b}m\033[48;2;{r_val};{g};{b}m{CHAR}")
            
        ascii_list.append("\033[0m\n")
        
    return "".join(ascii_list)

def get_youtube_urls(url):
    print("-> STEP 1: Analyzing YouTube video and filtering audio/video streams...")
    cmd = [
        "yt-dlp",
        "-g",
        "-f", "bv*[vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/b[vcodec^=avc1]",
        url
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"yt-dlp error: {result.stderr.strip()}")
    
    urls = result.stdout.strip().split('\n')
    return urls

def play_video(video_source, width=128, fps=12):
    parsed_url = urlparse(video_source)
    is_url = bool(parsed_url.scheme and parsed_url.netloc)
    is_youtube = "youtube.com" in video_source or "youtu.be" in video_source

    audio_process = None

    try:
        if is_youtube:
            urls = get_youtube_urls(video_source)
            video_url = urls[0]
            
            if len(urls) > 1:
                audio_url = urls[1]
                print("-> STEP 2: Launching YouTube audio in the background...")
                audio_process = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            
            print("-> STEP 3: Opening video stream in OpenCV...")
            cap = cv2.VideoCapture(video_url)
        else:
            if is_url:
                print(f"Opening internet stream: {video_source} ...")
                cap = cv2.VideoCapture(video_source)
            else:
                print(f"Opening local file: {video_source} ...")
                cap = cv2.VideoCapture(video_source)
                print("-> Launching local audio in the background...")
                audio_process = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", video_source],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        
        if not cap or not cap.isOpened():
            raise Exception("Error: OpenCV failed to open the video stream.")

        original_fps = cap.get(cv2.CAP_PROP_FPS)
        if original_fps <= 0: 
            original_fps = 24.0

        target_pause = 1.0 / fps

        print("-> STEP 4: Loading and synchronizing stream...")
        
        os.system('clear')
        # Start tracking time immediately when playback loop begins
        start_time = time.time()

        while cap.isOpened():
            # CALCULATE SYNC: Check how many seconds have actually passed
            elapsed_time = time.time() - start_time
            
            # Determine which video frame index SHOULD be playing right now
            expected_frame_index = int(elapsed_time * original_fps)
            current_frame_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

            # If video is lagging behind audio, catch up by grabbing and skipping old frames
            if current_frame_index < expected_frame_index:
                frames_to_skip = expected_frame_index - current_frame_index
                for _ in range(frames_to_skip):
                    cap.grab()

            ret, frame = cap.read()
            if not ret:
                break

            calculation_start = time.time()

            # Render ASCII graphics
            ascii_text = frame_to_ascii(frame, new_width=width, brightness=1.0)
            sys.stdout.write("\033[H")
            sys.stdout.write(ascii_text)
            sys.stdout.flush()

            # Dynamic precision pause
            calculation_time = time.time() - calculation_start
            actual_pause = target_pause - calculation_time
            
            if actual_pause > 0:
                time.sleep(actual_pause)
            
        cap.release()
        print("\n-> Stream finished.")

    except KeyboardInterrupt:
        print("\nPlayback stopped by user.")
    except Exception as e:
        sys.stdout.write("\033[0m")
        print("\n" + "="*50)
        print(" RUNTIME ERROR OCCURRED:")
        print(e)
        print("="*50 + "\n")
    finally:
        if audio_process is not None:
            audio_process.terminate()
            audio_process.wait()
        sys.stdout.write("\033[0m")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: vidtoascii <Path / URL> [width] [fps]")
    else:
        selected_width = 128
        selected_fps = 12
        
        if len(sys.argv) > 2:
            selected_width = int(sys.argv[2])
            
        if len(sys.argv) > 3:
            selected_fps = int(sys.argv[3])
            
        play_video(sys.argv[1], width=selected_width, fps=selected_fps)
