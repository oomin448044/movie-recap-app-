import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import time
import re
import subprocess

# --- Configuration ---
st.set_page_config(page_title="Burmese AI Movie Narrator Pro", layout="wide")

st.title("🎬 Burmese AI Movie Narrator Pro")
st.info("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.markdown("[Get API Key here](https://aistudio.google.com/app/apikey)")

# --- Functions ---
async def generate_burmese_audio(text, output_path):
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-5%", pitch="-2Hz")
    await communicate.save(output_path)

def find_working_model():
    try:
        models = genai.list_models()
        for m in models:
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name:
                return m.name
        return 'models/gemini-1.5-flash'
    except Exception:
        return 'models/gemini-1.5-flash'

def get_precise_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

# --- Main App ---
video_file = st.file_uploader("📁 Upload Movie Clip:", type=["mp4", "mov", "avi"])

video_path = None
audio_path = None
output_video_path = None
gen_file_name = None

if video_file and api_key:
    video_path = "input_video.mp4"
    with open(video_path, "wb") as f:
        f.write(video_file.read())

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            
            with st.status("AI is processing...", expanded=True) as status:
                st.write("🔍 Finding best available Gemini model...")
                model_name = find_working_model()
                model = genai.GenerativeModel(model_name)

                st.write("📤 Uploading video to AI...")
                gen_file = genai.upload_file(path=video_path, mime_type="video/mp4")
                gen_file_name = gen_file.name
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                st.write("📝 Generating natural Burmese narration...")
                prompt = """
                Analyze this movie clip and provide a BURMESE narration.
                STRICT RULES:
                1. Translate and narrate only what is happening in the video.
                2. NO introductions and NO conclusions.
                3. STYLE: Act like a professional human storyteller. 
                4. TONE: Conversational, emotional, and engaging.
                5. Use natural Burmese spoken language.
                FORMAT:
                [TITLES]
                (3 catchy titles)
                [RECAP]
                (The narration text only)
                """
                
                response = model.generate_content([gen_file, prompt])
                full_response = response.text

                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_path = "narration_audio.mp3"
                asyncio.run(generate_burmese_audio(recap_text, audio_path))

                # ✅ NEW: Remove silence at start (IMPORTANT)
                clean_audio = "clean_audio.mp3"
                subprocess.run([
                    "ffmpeg", "-i", audio_path,
                    "-af", "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-45dB",
                    clean_audio, "-y"
                ], check=True)
                audio_path = clean_audio

                st.write("🎬 Finalizing Video & Audio Sync (Frame-Perfect Mode)...")
                
                temp_video = "temp_video.mp4"
                subprocess.run([
                    "ffmpeg", "-i", video_path, "-r", "24", "-c:v", "libx264", 
                    "-pix_fmt", "yuv420p", "-preset", "ultrafast", temp_video, "-y"
                ], check=True)
                
                v_dur = get_precise_duration(temp_video)
                a_dur = get_precise_duration(audio_path)
                output_video_path = "final_output.mp4"
                
                if a_dur > v_dur:
                    cmd = [
                        "ffmpeg", "-i", temp_video, "-i", audio_path,
                        "-filter_complex",
                        f"[0:v]fps=24,tpad=stop_mode=clone:stop_duration={a_dur-v_dur},setsar=1:1[v];"
                        f"[1:a]adelay=200|200[a]",
                        "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", output_video_path, "-y"
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-i", temp_video, "-i", audio_path,
                        "-filter_complex",
                        f"[0:v]fps=24,setsar=1:1[v];"
                        f"[1:a]adelay=200|200[a]",
                        "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k", "-t", str(a_dur), output_video_path, "-y"
                    ]
                
                subprocess.run(cmd, check=True)

                status.update(label="✅ Complete!", state="complete")

            st.success("✨ Your Movie Recap is Ready!")
            st.video(output_video_path)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📌 Social Media Titles")
                for t in title_list[:3]:
                    if t.strip():
                        st.code(t.strip(), language="text")
            
            with col2:
                st.subheader("📥 Download")
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Final Video", f, file_name="burmese_movie_recap.mp4")

            if gen_file_name:
                genai.delete_file(gen_file_name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            temp_files = [video_path, audio_path, "temp_video.mp4", output_video_path]
            for f in temp_files:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
