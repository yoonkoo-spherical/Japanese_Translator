import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
import time
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment

# ==========================================
# 1. 기본 설정
# ==========================================
st.set_page_config(page_title="일본어 통역기", layout="centered")

# API 키 로드
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        st.stop()
except Exception:
    st.error("⚠️ Secrets 파일을 찾을 수 없습니다.")
    st.stop()

# 모델 설정
@st.cache_resource
def get_model():
    try:
        return genai.GenerativeModel('gemini-flash-latest')
    except:
        return genai.GenerativeModel('gemini-flash-latest')

model = get_model()

# ==========================================
# 2. 유틸리티 함수
# ==========================================

def ask_gemini(content):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return model.generate_content(content)
        except Exception as e:
            if "429" in str(e):
                time.sleep(2)
                continue
            else:
                st.error(f"오류: {e}")
                return None
    st.error("지연 발생. 잠시 후 다시 시도해주세요.")
    return None

def convert_audio_to_wav(audio_bytes):
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except:
        return io.BytesIO(audio_bytes)

def parse_response(text):
    parts = text.split('|')
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    return text, "", ""

# ==========================================
# 3. UI 디자인 함수 (가독성 UP 🚀)
# ==========================================

def display_jp_result(japanese, romaji, meaning):
    """
    일본어 결과를 위한 깔끔한 카드 UI (검은 글씨)
    """
    html_code = f"""
    <div style="
        padding: 20px;
        border-radius: 12px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    ">
        <p style="color: #666; font-size: 14px; margin-bottom: 5px;">🇯🇵 일본어 (번역)</p>
        <p style="color: #000000; font-size: 26px; font-weight: bold; margin-bottom: 8px; line-height: 1.4;">{japanese}</p>
        <div style="background-color: #f8f9fa; padding: 10px; border-radius: 8px;">
            <p style="color: #444; font-size: 16px; margin: 0;">🗣️ <b>{romaji}</b></p>
        </div>
        <p style="color: #888; font-size: 14px; margin-top: 10px; text-align: right;">뜻: {meaning}</p>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

def display_kr_result(korean):
    """
    한국어 결과를 위한 깔끔한 카드 UI (검은 글씨)
    """
    html_code = f"""
    <div style="
        padding: 20px;
        border-radius: 12px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    ">
        <p style="color: #666; font-size: 14px; margin-bottom: 5px;">🇰🇷 한국어 (번역)</p>
        <p style="color: #000000; font-size: 24px; font-weight: bold; margin: 0; line-height: 1.4;">{korean}</p>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

# ==========================================
# 4. 메인 화면 구성
# ==========================================

st.title("일본어 통역기")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 사진", "🎤 대화"])

# --- [Tab 1] 텍스트 번역 ---
with tab1:
    st.markdown("##### 🇰🇷 한국어 → 🇯🇵 일본어")
    text_input = st.text_area("번역할 내용을 입력하세요", height=100)
    
    if st.button("번역하기", key="btn_text", use_container_width=True):
        if text_input:
            with st.spinner("번역 중..."):
                prompt = f"""
                Translate Korean to Japanese naturally.
                Output format: Japanese Text|Romaji Pronunciation|Korean Meaning
                Input: {text_input}
                """
                response = ask_gemini(prompt)
                
                if response:
                    jp, rom, mean = parse_response(response.text)
                    display_jp_result(jp, rom, mean)

# --- [Tab 2] 사진 번역 ---
with tab2:
    st.markdown("##### 📸 메뉴판/안내문 해석")
    uploaded_file = st.file_uploader("이미지 선택", type=['jpg', 'png', 'webp'])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="선택된 이미지", use_column_width=True)
        
        if st.button("🔍 해석하기", use_container_width=True):
            with st.spinner("분석 중..."):
                prompt = """
                Find Japanese text and translate to Korean.
                Output format:
                1. [Summary]
                2. [Original Text] -> [Translation]
                """
                response = ask_gemini([prompt, image])
                if response:
                    # 사진 결과는 텍스트 양이 많으므로 기본 마크다운 사용 (가독성 위해 구분선 추가)
                    st.markdown("---")
                    st.markdown(response.text)

# --- [Tab 3] 음성 대화 (STT) ---
with tab3:
    col1, col2 = st.columns(2)
    
    # 한국어 입력 버튼
    with col1:
        st.info("🇰🇷 나 (한국어)")
        audio_kr = mic_recorder(start_prompt="🎤 말하기", stop_prompt="⏹️ 멈춤", key='kr', use_container_width=True)
        
    # 일본어 입력 버튼
    with col2:
        st.warning("🇯🇵 상대 (일본어)")
        audio_jp = mic_recorder(start_prompt="🎤 말하기", stop_prompt="⏹️ 멈춤", key='jp', use_container_width=True)

    # [Case 1] 한국어 음성 -> 일본어 텍스트
    if audio_kr:
        with st.spinner("인식 중..."):
            wav = convert_audio_to_wav(audio_kr['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as source:
                    audio_data = r.record(source)
                    stt = r.recognize_google(audio_data, language='ko-KR')
                    
                    # 내가 말한 내용 표시 (작게)
                    st.caption(f"나: {stt}")
                    
                    # 번역 요청
                    prompt = f"Translate to Japanese. Format: Japanese|Romaji|Meaning. Input: {stt}"
                    res = ask_gemini(prompt)
                    
                    if res:
                        jp, rom, mean = parse_response(res.text)
                        display_jp_result(jp, rom, mean)

            except Exception:
                st.error("음성 인식 실패. 다시 시도해주세요.")

    # [Case 2] 일본어 음성 -> 한국어 텍스트
    if audio_jp:
        with st.spinner("인식 중..."):
            wav = convert_audio_to_wav(audio_jp['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as source:
                    audio_data = r.record(source)
                    stt = r.recognize_google(audio_data, language='ja-JP')
                    
                    # 상대방 말한 내용 표시 (작게)
                    st.caption(f"상대: {stt}")
                    
                    # 번역 요청
                    res = ask_gemini(f"Translate Japanese to Korean: {stt}")
                    
                    if res:
                        display_kr_result(res.text)

            except Exception:
                st.error("음성 인식 실패. 다시 시도해주세요.")


