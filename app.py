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
    """FFprobe ကိုသုံးပြီး file ရဲ့ duration ကို အတိအကျ စက္ကန့်နဲ့ ရယူပါသည်"""
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

# Initialize file paths to None to avoid NameError in finally block
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
                
                try:
                    response = model.generate_content([gen_file, prompt])
                    full_response = response.text
                except Exception as e:
                    if "429" in str(e):
                        st.error("⚠️ Gemini API Quota ပြည့်သွားပါပြီ။ ခဏစောင့်ပြီးမှ ပြန်ကြိုးစားပေးပါ။ (သို့မဟုတ်) API Key အသစ်တစ်ခု အသုံးပြုပါ။")
                        st.stop()
                    else:
                        raise e

                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_path = "narration_audio.mp3"
                asyncio.run(generate_burmese_audio(recap_text, audio_path))

                st.write("🎬 Finalizing Video & Audio Sync (FFmpeg Direct Mode)...")
                
                # Duration များကို FFprobe ဖြင့် အတိအကျ စစ်ဆေးပါသည်
                v_dur = get_precise_duration(video_path)
                a_dur = get_precise_duration(audio_path)
                output_video_path = "final_output.mp4"
                
                if a_dur > v_dur:
                    # အသံက ပိုရှည်နေလျှင် (Freeze Logic)
                    freeze_duration = a_dur - v_dur
                    last_frame_path = "last_frame.jpg"
                    freeze_video_path = "freeze_video.mp4"
                    
                    # ၁။ နောက်ဆုံး frame ကို ပုံအဖြစ် ထုတ်ယူပါသည်
                    subprocess.run(["ffmpeg", "-sseof", "-0.1", "-i", video_path, "-update", "1", "-q:v", "1", last_frame_path, "-y"], check=True)
                    
                    # ၂။ အဲဒီပုံကို freeze video အဖြစ် ဖန်တီးပါသည် (24fps)
                    subprocess.run([
                        "ffmpeg", "-loop", "1", "-i", last_frame_path, 
                        "-c:v", "libx264", "-t", str(freeze_duration), 
                        "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", 
                        "-r", "24", freeze_video_path, "-y"
                    ], check=True)
                    
                    # ၃။ မူရင်းဗီဒီယိုနဲ့ freeze video ကို ပေါင်းစပ်ပြီး အသံထည့်ပါသည်
                    cmd = [
                        "ffmpeg", "-i", video_path, "-i", freeze_video_path, "-i", audio_path,
                        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                        "-map", "[v]", "-map", "2:a",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", output_video_path, "-y"
                    ]
                else:
                    # ဗီဒီယိုက ပိုရှည်နေလျှင် အသံပြီးဆုံးချိန်မှာ ဖြတ်ပါသည်
                    cmd = [
                        "ffmpeg", "-i", video_path, "-i", audio_path,
                        "-map", "0:v", "-map", "1:a",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k", "-t", str(a_dur), output_video_path, "-y"
                    ]
                
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    st.error(f"FFmpeg Error: {e.stderr.decode()}")
                    raise

                status.update(label="✅ Complete!", state="complete")

            st.success("✨ Your Movie Recap is Ready!")
            st.video(output_video_path)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📌 Social Media Titles")
                for t in title_list[:3]:
                    if t.strip(): st.code(t.strip(), language="text")
            
            with col2:
                st.subheader("📥 Download")
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Final Video", f, file_name="burmese_movie_recap.mp4")

            # Cleanup Gemini file
            if gen_file_name:
                genai.delete_file(gen_file_name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            # Safe cleanup of local files
            temp_files = [video_path, audio_path, "last_frame.jpg", "freeze_video.mp4", "final_output.mp4"]
            for f in temp_files:
                if f and os.path.exists(f):
                    try: os.remove(f)
                    except: pass
