import streamlit as st
import os
import time
import tempfile
from google import genai
from dotenv import load_dotenv

# 1. 기본 설정 및 환경 변수 로드
load_dotenv()

st.set_page_config(
    page_title="Gemini PDF Researcher",
    page_icon="📚",
    layout="wide"
)

# 2. 사이드바: API 키 및 설정
with st.sidebar:
    st.header("설정")
    env_key = os.getenv("GEMINI_API_KEY")
    api_key = st.text_input("Gemini API Key", value=env_key if env_key else "", type="password")
    
    st.divider()
    st.write("사용 모델: `gemini-flash-latest`")
    st.info("PDF를 드래그 앤 드롭하면 분석합니다.")

# 3. [핵심] 클라이언트 객체 캐싱 함수
# 이 함수는 입력값(api_key)이 같으면 메모리에 저장된 client 객체를 재사용합니다.
# 이를 통해 Streamlit이 재실행될 때 연결이 끊기는 문제를 방지합니다.
@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)

# 4. 메인 로직
st.title("📚 PDF 논문 통합 분석 & 채팅")

# 세션 상태 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "processed_files" not in st.session_state:
    st.session_state.processed_files = []

# API 클라이언트 초기화 (캐싱된 함수 사용)
if api_key:
    try:
        client = get_gemini_client(api_key)
    except Exception as e:
        st.error(f"API 연결 오류: {e}")
        st.stop()
else:
    st.warning("왼쪽 사이드바에 API 키를 입력해주세요.")
    st.stop()

# 5. 파일 업로드 영역
uploaded_files = st.file_uploader(
    "PDF 파일을 이곳에 드래그 하세요", 
    type=["pdf"], 
    accept_multiple_files=True
)

# 6. 파일 처리 및 초기 분석
if uploaded_files and st.button("파일 분석 시작"):
    # 이미
