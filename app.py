import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import os

# ==========================================
# 1. 페이지 테마 및 스타일 설정
# ==========================================
st.set_page_config(page_title="Rohto Mentholatum Inventory System", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    .stApp { background-color: #f8f9fa; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 시트 2개(재고, 매핑) 동시 로드
# ==========================================
@st.cache_data(ttl=600) # 10분마다 자동으로 구글 시트 최신화
def load_data_from_gsheets():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 1️⃣ 매일 갱신되는 원본 '재고' 구글 시트 불러오기 (첫 번째 링크)
        # (주의: 만약 두 링크의 역할이 반대라면 URL 위치만 서로 바꿔주세요)
        stock_url = "https://docs.google.com/spreadsheets/d/1wuS9xiYqtepX8k13IQeEREwyowh9Jsh_gAt_MFdTjKA/edit?gid=2041758552#gid=2041758552"
       df_stock = conn.read(spreadsheet=stock_url, worksheet="Stock")
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        # 2️⃣ 팀원들이 관리하는 '매핑용' 구글 시트 불러오기 (두 번째 링크)
        mapping_url = "https://docs.google.com/spreadsheets/d/1mQbJ_H1KOGPD1wNQdIN1cpmLSn_iBbb0iLFLctMMtJc/edit?gid=230529674#gid=230529674"
        df_channel = conn.read(spreadsheet=mapping_url, worksheet="Sheet2") # 엑셀 하단 탭 이름
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        # --- (이하 기존 병합 및 전처리 로직 100% 동일) ---
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        cols_to_bring = ['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']
        if '용량' in df_channel.columns:
            cols_to_bring.append('용량')
            
        mapping_sub = df_channel[cols_to_bring].dropna(subset=['제품코드_key']).drop_duplicates('제품코드_key')
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드_key", right_on="제품코드_key", how="left")
        
        df_merged.rename(columns={
            'Customer': '납품처', '상품코드': '제품코드', '화주LOT': '로트번호',
            '환산': '수량', 'Remarks': '특이사항', 'Sales Team': '영업팀', 'Channel': '채널'
        }, inplace=True)

        if '용량' not in df_merged.columns:
            df_merged['용량'] = df_merged.get('용량(L)', '-')
        
        df_merged['용량'] = df_merged['용량'].fillna('-').astype(str).str.strip()
        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[(df_merged['로트번호'] != '') & (df_merged['로트번호'].str.lower() != 'nan')]
        
        exclude_lots = '임시적치|불량|ZPK|약국반품|폐기|회송예정'
        df_merged = df_merged[~df_merged['로트번호'].str.contains(exclude_lots, case=False, na=False)]
        
        df_merged['납품처'] = df_merged['납품처'].fillna('미지정').astype(str).str.strip()
        df_merged['영업팀'] = df_merged['영업팀'].fillna('미분류').astype(str).str.strip()
        df_merged['특이사항'] = df_merged['특이사항'].fillna('').astype(str).str.strip()

        if '상품바코드' in df_merged.columns:
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'[?？]', '', regex=True).str.strip()
        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"구글 시트 연동 중 에러가 발생했습니다: {e}")
        st.info("💡 힌트: 구글 시트의 링크가 정확한지, 그리고 각 파일의 하단 시트 탭 이름('재고현황', 'Sheet2')이 일치하는지 확인해주세요.")
        return None

# ==========================================
# 3. 사이드바 UI (수동 업로드 완전 제거)
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", width=200)
    else: st.subheader("Mentholatum")
    st.markdown("---")
    
    st.subheader("🔄 Data Sync")
    # 파일 업로드 대신 '새로고침' 버튼으로 대체
    if st.button("클라우드 최신 재고 동기화", type="primary", use_container_width=True):
        st.cache_data.clear() # 캐시 삭제 후 새로 읽기
        st.success("데이터가 최신화되었습니다!")
        
    st.markdown("<div style='border-bottom: 1px solid #eaeaea; margin: 12px 0;'></div>", unsafe_allow_html=True)
    st.subheader("Filter Option")
    
    # (앱 실행 및 필터링 로직)
    df_raw = load_data_from_gsheets()
    if df_raw is None or df_raw.empty:
        st.stop()

    is_exclusive = st.toggle("🌟 전용 납품 품목만 보기")
    
    customer_set = set(part.strip() for c in df_raw['납품처'].dropna() for part in str(c).split(',') if part.strip())
    selected_customer = st.selectbox("🏢 납품처", ["전체"] + sorted(list(customer_set)))
    
    team_set = set(part.strip() for t in df_raw['영업팀'].dropna() for part in str(t).split(',') if part.strip())
    selected_team = st.selectbox("👥 영업팀", ["전체"] + sorted(list(team_set)))
    
    search_q = st.text_input("🔍 Search", placeholder="제품명 또는 코드")

# 필터 적용
df_filtered = df_raw.copy()
if is_exclusive: df_filtered = df_filtered[~df_filtered['납품처'].astype(str).str.contains(',', na=False)]
if selected_customer != "전체": df_filtered = df_filtered[df_filtered['납품처'].apply(lambda x: selected_customer in [c.strip() for c in str(x).split(',')])]
if selected_team != "전체": df_filtered = df_filtered[df_filtered['영업팀'].apply(lambda x: selected_team in [t.strip() for t in str(x).split(',')])]
if search_q: df_filtered = df_filtered[df_filtered['상품명'].str.contains(search_q, case=False, na=False) | df_filtered['제품코드'].str.contains(search_q, case=False, na=False)]

# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
st.title("Inventory Mastering Dashboard")

if not df_filtered.empty:
    df_main = df_filtered.groupby(['상품바코드', '제품코드']).agg({
        '상품명': 'first', '납품처': 'first', '영업팀': 'first', '특이사항': 'first', 
        '수량': 'sum', '용량': 'first'
    }).reset_index()
    
    df_main.rename(columns={'수량': '총 재고'}, inplace=True)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("총 취급 품목수", f"{len(df_main)} SKUs")
    m2.metric("총 가용 수량", f"{df_main['총 재고'].sum():,} EA")
    
    st.markdown("---")
    st.dataframe(df_main, use_container_width=True, hide_index=True)
else:
    st.warning("조회된 재고 데이터가 없습니다.")
