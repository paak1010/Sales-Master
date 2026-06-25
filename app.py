import streamlit as st
import pandas as pd
from io import BytesIO
import os
from PIL import Image, ImageOps

# ==========================================
# 1. 페이지 테마 및 스타일 설정
# ==========================================
st.set_page_config(
    page_title="Rohto Mentholatum Inventory System",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    .stApp { background-color: #f8f9fa; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    .stButton > button { width: 100%; background-color: #ffffff; color: #006838; border: 1px solid #006838; border-radius: 4px; font-weight: 600; transition: 0.3s; }
    .stButton > button:hover { background-color: #006838; color: #ffffff; }
    h1 { color: #1a1a1a; font-weight: 800; letter-spacing: -1px; }
    h3 { color: #006838; font-weight: 700; }
    [data-testid="stDataFrame"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 이미지 처리 및 상세 팝업창 함수
# ==========================================
def process_uniform_image(img_path, size=(500, 500)):
    try:
        img = Image.open(img_path)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        else:
            img = img.convert('RGB')
        img = ImageOps.pad(img, size, color=(255, 255, 255))
        return img
    except Exception:
        return None

@st.dialog("📋 제품 상세 및 로트 명세", width="large")
def show_lot_details(df_detail, product_name, capacity, product_code):
    st.markdown(f"<h3 style='font-size: 24px; color: #006838; margin-bottom: 20px;'>📦 {product_name}</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2.5])
    
    with c1:
        image_displayed = False
        valid_exts = ['.jpg', '.jpeg', '.png', '.JPG', '.PNG', '.webp']
        
        for ext in valid_exts:
            paths_to_check = [
                f"{product_code}{ext}", 
                f"images/{product_code}{ext}", 
                f"images2/{product_code}{ext}"
            ]
            for path in paths_to_check:
                if os.path.exists(path):
                    uniform_img = process_uniform_image(path)
                    if uniform_img:
                        st.image(uniform_img, use_container_width=True)
                        image_displayed = True
                        break
            if image_displayed: break
                
        if not image_displayed:
            st.image("https://www.rohto.co.kr/common/images/logo.png", use_container_width=True)
            
        display_cap = str(capacity).strip() if str(capacity) not in ['0', '0.0', 'nan', '', '-'] else "정보 없음"
        st.markdown(f"""
            <div style='text-align: center; padding: 10px; background-color: #f1f8f5; border-radius: 8px; margin-top: 10px;'>
                <span style='font-size: 14px; color: #555;'>규격/용량</span><br>
                <strong style='font-size: 18px; color: #006838;'>{display_cap}</strong>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        merged_detail = df_detail.groupby(['로트번호', '유효일자', '잔여일수'], dropna=False, as_index=False)['수량'].sum()
        merged_detail = merged_detail.sort_values(by='잔여일수').reset_index(drop=True)
        merged_detail.rename(columns={'수량': '합산 수량'}, inplace=True)
        styled_df = merged_detail.style.set_properties(**{'font-size': '16px', 'font-weight': '500'})

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "잔여일수": st.column_config.ProgressColumn("유통기한 잔여", format="%d일", min_value=0, max_value=1095),
                "합산 수량": st.column_config.NumberColumn("가용 재고", format="%d EA"),
                "유효일자": st.column_config.DateColumn("유효일자")
            }
        )
        st.markdown("<p style='font-size: 14px; color: gray;'>※ 정보(로트/유효일/잔여일)가 완벽히 동일한 데이터는 자동으로 합산 표시됩니다.</p>", unsafe_allow_html=True)

# ==========================================
# 3. 구글 시트 데이터 로드 및 전처리
# ==========================================
@st.cache_data(ttl=600)
def load_data_from_gsheets():
    try:
        # 1️⃣ 원본 재고 시트 (header=2 적용: 3번째 줄부터 실제 컬럼 제목으로 인식)
        stock_csv_url = "https://docs.google.com/spreadsheets/d/1wuS9xiYqtepX8k13IQeEREwyowh9Jsh_gAt_MFdTjKA/export?format=csv&gid=2041758552"
        df_stock = pd.read_csv(stock_csv_url, header=2)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        # 2️⃣ 매핑용 시트 (얘는 첫 줄이 제목이 맞음)
        mapping_csv_url = "https://docs.google.com/spreadsheets/d/1mQbJ_H1KOGPD1wNQdIN1cpmLSn_iBbb0iLFLctMMtJc/export?format=csv&gid=230529674"
        df_channel = pd.read_csv(mapping_csv_url)
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        # --- 전처리 로직 ---
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        cols_to_bring = ['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']
        if '용량' in df_channel.columns:
            cols_to_bring.append('용량')
            
        mapping_sub = df_channel[cols_to_bring].dropna(subset=['제품코드_key']).drop_duplicates('제품코드_key')
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드_key", right_on="제품코드_key", how="left")
        
        # 이름 변경 (엑셀 원본에 맞게 유연하게 매핑)
        df_merged.rename(columns={
            'Customer': '납품처', '상품코드': '제품코드', '화주LOT': '로트번호',
            'Remarks': '특이사항', 'Sales Team': '영업팀', 'Channel': '채널'
        }, inplace=True)

        # 수량 컬럼 찾기 (사진의 '합계 : 환산' 또는 기존 '환산')
        if '합계 : 환산' in df_merged.columns:
            df_merged.rename(columns={'합계 : 환산': '수량'}, inplace=True)
        elif '환산' in df_merged.columns:
            df_merged.rename(columns={'환산': '수량'}, inplace=True)

        # 수량과 잔여일수 안전하게 숫자로 변환
        if '수량' in df_merged.columns:
            df_merged['수량'] = pd.to_numeric(df_merged['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        if '잔여일수' in df_merged.columns:
            df_merged['잔여일수'] = pd.to_numeric(df_merged['잔여일수'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

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
        st.error(f"데이터 연동 중 오류가 발생했습니다: {e}")
        return None

# ==========================================
# 4. 사이드바 UI & 필터링
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", width=200)
    else: st.subheader("Mentholatum")
    st.markdown("---")
    
    st.subheader("🔄 Data Sync")
    if st.button("클라우드 최신 재고 동기화", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.success("데이터가 최신화되었습니다!")
        
    st.markdown("<div style='border-bottom: 1px solid #eaeaea; margin: 12px 0;'></div>", unsafe_allow_html=True)
    st.subheader("Filter Option")
    
    df_raw = load_data_from_gsheets()
    if df_raw is None or df_raw.empty:
        st.stop()

    is_exclusive = st.toggle("🌟 전용 납품 품목만 보기")
    
    customer_set = set(part.strip() for c in df_raw['납품처'].dropna() for part in str(c).split(',') if part.strip())
    selected_customer = st.selectbox("🏢 납품처", ["전체"] + sorted(list(customer_set)))
    
    team_set = set(part.strip() for t in df_raw['영업팀'].dropna() for part in str(t).split(',') if part.strip())
    selected_team = st.selectbox("👥 영업팀", ["전체"] + sorted(list(team_set)))
    
    search_q = st.text_input("🔍 Search", placeholder="제품명 또는 코드")

df_filtered = df_raw.copy()
if is_exclusive: df_filtered = df_filtered[~df_filtered['납품처'].astype(str).str.contains(',', na=False)]
if selected_customer != "전체": df_filtered = df_filtered[df_filtered['납품처'].apply(lambda x: selected_customer in [c.strip() for c in str(x).split(',')])]
if selected_team != "전체": df_filtered = df_filtered[df_filtered['영업팀'].apply(lambda x: selected_team in [t.strip() for t in str(x).split(',')])]
if search_q: df_filtered = df_filtered[df_filtered['상품명'].str.contains(search_q, case=False, na=False) | df_filtered['제품코드'].str.contains(search_q, case=False, na=False)]

# ==========================================
# 5. 메인 대시보드 출력
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
    m2.metric("총 가용 수량", f"{int(df_main['총 재고'].sum()):,} EA")
    
    st.markdown("---")
    
    grid_ratio = [1.5, 1.2, 1.5, 3.5, 1.2, 2.0, 1.0]
    cols = st.columns(grid_ratio)
    fields = ['납품처', '영업팀', '제품코드', '상품명', '현재 재고', '특이사항', 'Action']
    for col, field in zip(cols, fields): col.markdown(f"**{field}**")
    st.markdown("<div style='border-bottom: 2px solid #006838; margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    for idx, row in df_main.iterrows():
        with st.container():
            r_cols = st.columns(grid_ratio)
            r_cols[0].write(row['납품처'])
            r_cols[1].write(row['영업팀'])
            r_cols[2].write(row['제품코드'])
            r_cols[3].write(f"**{row['상품명']}**")
            r_cols[4].write(f"{int(row['총 재고']):,}")
            r_cols[5].write(f"<small>{row['특이사항']}</small>", unsafe_allow_html=True)
            
            if r_cols[6].button("상세", key=f"v_{idx}"):
                df_detail = df_filtered[
                    (df_filtered['상품바코드'] == row['상품바코드']) & 
                    (df_filtered['제품코드'] == row['제품코드'])
                ][['로트번호', '유효일자', '잔여일수', '수량']]
                show_lot_details(df_detail, row['상품명'], row['용량'], row['제품코드'])
else:
    st.warning("조회된 재고 데이터가 없습니다.")
