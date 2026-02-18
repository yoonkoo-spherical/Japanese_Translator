import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
import time
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment

# ==========================================
# 1. 환경 설정 및 세션 상태 초기화
# ==========================================
st.set_page_config(page_title="안정화 AI 통역기", layout="centered")

# 중복 실행 방지를 위한 세션 상태 관리
if "last_request_time" not in st.session_state:
    st.session_state.last_request_time = 0

# API 키 설정
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        st.stop()
except Exception:
    st.error("⚠️ Secrets 설정 오류가 발생했습니다.")
    st.stop()

# 모델 설정 (요청하신 gemini-flash-latest 사용)
@st.cache_resource
def get_model():
    return genai.GenerativeModel(
        model_name='gemini-2.0-flash-lite',
        generation_config={
            "temperature": 0.1,  # 속도 및 일관성을 위해 낮게 설정
            "max_output_tokens": 1024,
        }
    )

model = get_model()

# ==========================================
# 2. 핵심 로직: 429 및 무한루프 방지
# ==========================================

def ask_gemini_safe(content):
    """
    중복 호출을 방지하고 타임아웃을 적용한 안전한 API 호출 함수
    """
    # 1. 너무 짧은 간격(2초 이내)의 중복 호출 차단
    current_time = time.time()
    if current_time - st.session_state.last_request_time < 2:
        return None
    
    st.session_state.last_request_time = current_time

    try:
        # 10초 내 응답 없으면 끊기 (수 분간 대기하는 현상 방지)
        response = model.generate_content(
            content, 
            request_options={"timeout": 15}
        )
        return response
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ 현재 요청이 많습니다. 10초만 기다려주세요.")
        elif "deadline" in str(e).lower():
            st.error("⏰ 연결 시간이 초과되었습니다. 다시 시도해 주세요.")
        else:
            st.error(f"❌ 오류가 발생했습니다: {e}")
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
# 3. 시각적 가독성을 높인 결과 표시 (검은 글씨 카드)
# ==========================================

def display_result_card(title, main_text, sub_text=None, footer=None):
    html_code = f"""
    <div style="padding: 20px; border-radius: 12px; background-color: #ffffff; 
                border: 1px solid #e0e0e0; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <p style="color: #666; font-size: 14px; margin-bottom: 5px;">{title}</p>
        <p style="color: #000000; font-size: 26px; font-weight: bold; margin-bottom: 8px; line-height: 1.4;">{main_text}</p>
        {f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 8px;"><p style="color: #444; font-size: 16px; margin: 0;"><b>{sub_text}</b></p></div>' if sub_text else ''}
        {f'<p style="color: #888; font-size: 13px; margin-top: 10px; text-align: right;">{footer}</p>' if footer else ''}
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

# ==========================================
# 4. UI 레이아웃
# ==========================================

st.title("일본어 실시간 통역기")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📸 사진", "🎤 대화"])

with tab1:
    text_input = st.text_area("한국어 내용을 입력하세요", height=100, key="text_input_area")
    if st.button("번역하기", use_container_width=True):
        if text_input:
            with st.spinner("번역 중..."):
                prompt = f"Translate Korean to Japanese. Format: Japanese|Romaji|Meaning. Input: {text_input}"
                res = ask_gemini_safe(prompt)
                if res:
                    jp, rom, mean = parse_response(res.text)
                    display_result_card("🇯🇵 일본어 번역 결과", jp, rom, f"뜻: {mean}")

with tab2:
    uploaded_file = st.file_uploader("사진 업로드", type=['jpg', 'png', 'webp'])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_column_width=True)
        if st.button("사진 속 일본어 해석", use_container_width=True):
            with st.spinner("이미지 분석 중..."):
                prompt = "Find Japanese text and translate to Korean. Format: 1. [Summary] 2. [Original] -> [Translation]"
                res = ask_gemini_safe([prompt, img])
                if res:
                    st.markdown("---")
                    st.markdown(res.text)

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.info("🇰🇷 나 (한국어)")
        audio_kr = mic_recorder(start_prompt="🎤 말하기", stop_prompt="⏹️ 멈춤", key='kr_mic')
    with col2:
        st.warning("🇯🇵 상대 (일본어)")
        audio_jp = mic_recorder(start_prompt="🎤 말하기", stop_prompt="⏹️ 멈춤", key='jp_mic')

    # 한국어 음성 처리
    if audio_kr:
        with st.spinner("음성 인식 중..."):
            wav = convert_audio_to_wav(audio_kr['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as source:
                    audio_data = r.record(source)
                    stt = r.recognize_google(audio_data, language='ko-KR')
                    st.caption(f"인식된 내용: {stt}")
                    
                    res = ask_gemini_safe(f"Translate to Japanese. Format: Japanese|Romaji|Meaning. Input: {stt}")
                    if res:
                        jp, rom, mean = parse_response(res.text)
                        display_result_card("🇯🇵 통역 결과", jp, rom, f"뜻: {mean}")
            except Exception:
                st.error("인식에 실패했습니다.")

    # 일본어 음성 처리
    if audio_jp:
        with st.spinner("음성 인식 중..."):
            wav = convert_audio_to_wav(audio_jp['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as source:
                    audio_data = r.record(source)
                    stt = r.recognize_google(audio_data, language='ja-JP')
                    st.caption(f"인식된 내용: {stt}")
                    
                    res = ask_gemini_safe(f"Translate Japanese to Korean: {stt}")
                    if res:
                        display_result_card("🇰🇷 한국어 번역 결과", res.text)
            except Exception:
                st.error("인식에 실패했습니다.")


