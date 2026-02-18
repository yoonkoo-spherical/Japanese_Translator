import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
from streamlit_mic_recorder import mic_recorder

# 1. 페이지 설정 (모바일 화면 최적화)
st.set_page_config(page_title="Gemini 일본어 번역기", layout="centered")

# 2. API 키 보안 로드
# 로컬에서는 .streamlit/secrets.toml을, 배포 환경에서는 Streamlit Secrets를 참조
try:
    if "GEMINI_API_KEY" in st.secrets:
        GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=GENAI_API_KEY)
    else:
        st.error("API 키가 설정되지 않았습니다. Streamlit 설정을 확인하세요.")
        st.stop()
except FileNotFoundError:
    st.error("Secrets 파일을 찾을 수 없습니다.")
    st.stop()

# 3. Gemini 모델 설정 (Gemini 1.5 Flash 사용 - 속도 및 비용 효율성)
@st.cache_resource
def get_model():
    return genai.GenerativeModel('gemini-1.5-flash')

model = get_model()

# 4. UI 헤더
st.title("🇯🇵 AI 일본어 통역기")
st.caption("Gemini 1.5 Flash 기반 (텍스트 / 갤러리 사진 / 음성)")

# 5. 탭 구성
tab1, tab2, tab3 = st.tabs(["📝 텍스트", "🖼️ 사진(갤러리)", "🎤 음성 대화"])

# --- [기능 1] 텍스트 번역 ---
with tab1:
    st.markdown("##### 🇰🇷 한국어 ↔ 🇯🇵 일본어")
    text_input = st.text_area("내용을 입력하세요 (자동 감지)", height=150)
    
    if st.button("번역하기", key="btn_text"):
        if text_input:
            with st.spinner("Gemini가 번역 중입니다..."):
                try:
                    prompt = f"""
                    You are a professional translator.
                    Translate the following text naturally.
                    - If the input is Korean, translate it to Japanese.
                    - If the input is Japanese, translate it to Korean.
                    
                    Input text: {text_input}
                    """
                    response = model.generate_content(prompt)
                    st.success(response.text)
                except Exception as e:
                    st.error(f"오류 발생: {e}")

# --- [기능 2] 사진 번역 (Gemini Vision) ---
with tab2:
    st.markdown("##### 📸 사진을 업로드하면 텍스트를 추출하여 번역합니다")
    # 모바일에서는 이 위젯을 누르면 '카메라'와 '미디어(갤러리)' 중 선택 가능
    uploaded_file = st.file_uploader("이미지 선택", type=['jpg', 'jpeg', 'png', 'webp'])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="선택된 이미지", use_column_width=True)
        
        if st.button("🔍 분석 및 번역 요청"):
            with st.spinner("이미지 분석 중..."):
                try:
                    # 이미지와 프롬프트를 함께 전달
                    image_prompt = """
                    이 이미지 내의 일본어 텍스트를 모두 찾아서 한국어로 번역해 주세요.
                    여행자가 이해하기 쉽도록 다음 형식으로 출력해 주세요:
                    
                    1. [핵심 내용 요약]
                    2. [주요 텍스트 원문] -> [한국어 번역]
                    """
                    response = model.generate_content([image_prompt, image])
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"이미지 처리 중 오류 발생: {e}")

# --- [기능 3] 음성 통역 (STT + Gemini) ---
with tab3:
    st.markdown("##### 🎤 말하면 번역해줍니다")
    
    col1, col2 = st.columns(2)
    
    # 한국어 녹음
    with col1:
        st.info("🇰🇷 나 (한국어)")
        audio_kr = mic_recorder(
            start_prompt="🔴 말하기",
            stop_prompt="⏹️ 멈춤",
            key='recorder_kr',
            just_once=False,
            use_container_width=True
        )

    # 일본어 녹음
    with col2:
        st.warning("🇯🇵 상대 (일본어)")
        audio_jp = mic_recorder(
            start_prompt="🔴 말하기",
            stop_prompt="⏹️ 멈춤",
            key='recorder_jp',
            just_once=False,
            use_container_width=True
        )

    # 한국어 음성 처리 로직
    if audio_kr:
        with st.spinner("음성 인식 및 번역 중..."):
            audio_bytes = io.BytesIO(audio_kr['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(audio_bytes) as source:
                    audio_data = r.record(source)
                    # 1. Google STT (Speech-to-Text)
                    stt_text = r.recognize_google(audio_data, language='ko-KR')
                    st.write(f"🗣️ 인식됨: **{stt_text}**")
                    
                    # 2. Gemini 번역
                    trans_prompt = f"Translate this Korean text to Japanese naturally for conversation: {stt_text}"
                    response = model.generate_content(trans_prompt)
                    st.success(f"🇯🇵 번역: {response.text}")
            except Exception:
                st.error("음성을 명확히 인식하지 못했습니다. 다시 시도해주세요.")

    # 일본어 음성 처리 로직
    if audio_jp:
        with st.spinner("음성 인식 및 번역 중..."):
            audio_bytes = io.BytesIO(audio_jp['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(audio_bytes) as source:
                    audio_data = r.record(source)
                    # 1. Google STT (Speech-to-Text)
                    stt_text = r.recognize_google(audio_data, language='ja-JP')
                    st.write(f"🗣️ 인식됨: **{stt_text}**")
                    
                    # 2. Gemini 번역
                    trans_prompt = f"Translate this Japanese text to Korean naturally for conversation: {stt_text}"
                    response = model.generate_content(trans_prompt)
                    st.success(f"🇰🇷 번역: {response.text}")
            except Exception:
                st.error("음성을 명확히 인식하지 못했습니다. 다시 시도해주세요.")
