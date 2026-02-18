import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
import streamlit.components.v1 as components  # 👈 자바스크립트 실행을 위해 필요
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment

# 1. 페이지 설정
st.set_page_config(page_title="초고속 AI 통역사", layout="centered")

# 2. API 키 설정
try:
    if "GEMINI_API_KEY" in st.secrets:
        GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=GENAI_API_KEY)
    else:
        st.error("API 키 설정을 확인하세요.")
        st.stop()
except Exception:
    st.error("Secrets 파일을 찾을 수 없습니다.")
    st.stop()

# 3. 모델 설정
@st.cache_resource
def get_model():
    return genai.GenerativeModel('gemini-flash-lite-latest')

model = get_model()

# --- 🚀 핵심 기능: 브라우저 내장 TTS (즉시 재생) ---
def autoplay_audio(text, lang='ja'):
    """
    파이썬이 아니라 사용자의 브라우저(크롬/사파리)에게 
    '이거 읽어!'라고 명령하는 자바스크립트 코드를 심습니다.
    """
    js_code = f"""
    <script>
        var msg = new SpeechSynthesisUtterance("{text}");
        msg.lang = "{'ja-JP' if lang == 'ja' else 'ko-KR'}";
        msg.rate = 1.0; // 속도
        window.speechSynthesis.speak(msg);
    </script>
    """
    # 화면에는 보이지 않게(height=0) 스크립트만 실행
    components.html(js_code, height=0)

# --- 오디오 변환 함수 (입력용) ---
def convert_audio_to_wav(audio_bytes):
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except:
        return io.BytesIO(audio_bytes)

def parse_gemini_response(text):
    parts = text.split('|')
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    return text, "", ""

# --- UI 시작 ---
st.title("⚡ 초고속 AI 통역사")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 사진", "🎤 음성"])

# [기능 1] 텍스트 번역
with tab1:
    text_input = st.text_area("한국어 입력", height=100)
    if st.button("번역 및 듣기"):
        if text_input:
            with st.spinner(".."):
                try:
                    prompt = f"Translate Korean to Japanese. Format: Japanese|Romaji|Meaning. Input: {text_input}"
                    response = model.generate_content(prompt)
                    jp, romaji, mean = parse_gemini_response(response.text)
                    
                    st.success(f"🇯🇵 {jp}")
                    st.info(f"발음: {romaji}")
                    st.caption(f"뜻: {mean}")
                    
                    # 🚀 즉시 재생 (파일 생성 X)
                    autoplay_audio(jp, 'ja')
                    
                except Exception as e:
                    st.error(f"Error: {e}")

# [기능 2] 사진 번역
with tab2:
    uploaded_file = st.file_uploader("사진", type=['jpg', 'png', 'webp'])
    if uploaded_file and st.button("해석"):
        with st.spinner(".."):
            image = Image.open(uploaded_file)
            st.image(image, use_column_width=True)
            res = model.generate_content(["Find Japanese text, translate to Korean.", image])
            st.markdown(res.text)

# [기능 3] 음성 통역
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.info("🇰🇷 나")
        audio_kr = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️", key='kr')
    with col2:
        st.warning("🇯🇵 상대")
        audio_jp = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️", key='jp')

    # 내가 말할 때 (한국어 -> 일본어 듣기)
    if audio_kr:
        with st.spinner("통역 중.."):
            wav = convert_audio_to_wav(audio_kr['bytes'])
            r = sr.Recognizer()
            with sr.AudioFile(wav) as source:
                try:
                    audio = r.record(source)
                    stt = r.recognize_google(audio, language='ko-KR')
                    st.write(f"🗣️ 나: {stt}")
                    
                    res = model.generate_content(f"Translate to Japanese: {stt}. Format: Japanese|Romaji|Meaning")
                    jp, rom, _ = parse_gemini_response(res.text)
                    
                    st.success(f"🇯🇵 {jp}")
                    st.caption(f"발음: {rom}")
                    
                    # 🚀 일본어로 즉시 말하기
                    autoplay_audio(jp, 'ja')
                except:
                    st.error("인식 실패")

    # 상대가 말할 때 (일본어 -> 한국어 듣기)
    if audio_jp:
        with st.spinner("통역 중.."):
            wav = convert_audio_to_wav(audio_jp['bytes'])
            r = sr.Recognizer()
            with sr.AudioFile(wav) as source:
                try:
                    audio = r.record(source)
                    stt = r.recognize_google(audio, language='ja-JP')
                    st.write(f"🗣️ 상대: {stt}")
                    
                    res = model.generate_content(f"Translate Japanese to Korean: {stt}")
                    kr_text = res.text
                    
                    st.success(f"🇰🇷 {kr_text}")
                    
                    # 🚀 한국어로 즉시 말하기
                    autoplay_audio(kr_text, 'ko')
                except:
                    st.error("인식 실패")
