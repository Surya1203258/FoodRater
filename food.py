import streamlit as st
import sqlite3
import os
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

# ---------- CONFIG ----------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_NAME = "reviews.db"

# ---------- DATABASE ----------
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating TEXT
            )
        """)

        cols = [row[1] for row in conn.execute("PRAGMA table_info(reviews)")]

        if "english_text" not in cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN english_text TEXT")
        if "telugu_text" not in cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN telugu_text TEXT")
        if "ai_review" not in cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN ai_review TEXT")
        if "timestamp" not in cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN timestamp TEXT")

def save_review(rating, english, telugu, ai_review):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            INSERT INTO reviews (rating, english_text, telugu_text, ai_review, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            rating,
            english,
            telugu,
            ai_review,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

def get_reviews():
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("""
            SELECT id, rating, english_text, telugu_text, ai_review, timestamp
            FROM reviews
            ORDER BY id DESC
        """).fetchall()

def delete_review(review_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))

def delete_all_reviews():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM reviews")

# ---------- AI ----------
def transcribe_audio(audio):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio.read())
        path = tmp.name

    result = client.audio.transcriptions.create(
        file=open(path, "rb"),
        model="gpt-4o-transcribe"
    )
    return result.text

def translate(text, language):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Translate the following into {language}."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content

def clean_review(english_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Rewrite this food review into polite, simple, respectful feedback "
                    "for public display."
                )
            },
            {"role": "user", "content": english_text}
        ]
    )
    return response.choices[0].message.content

def analyze_common_issues(reviews_data):
    """Analyze reviews to identify common issues"""
    if not reviews_data:
        return "No reviews available for analysis."
    
    # Combine all review texts
    all_reviews = "\n".join([f"Rating: {r[1]}, Review: {r[2]}" for r in reviews_data if r[2]])
    
    if not all_reviews.strip():
        return "No review text available for analysis."
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Analyze the following food reviews and identify the most common issues, "
                    "complaints, or problems mentioned across all reviews. "
                    "Provide a concise summary of 3-5 key issues. "
                    "Focus on actionable feedback like taste, quality, service, temperature, etc."
                )
            },
            {"role": "user", "content": f"Reviews:\n{all_reviews}"}
        ]
    )
    return response.choices[0].message.content

# ---------- UI ----------
st.set_page_config(
    page_title="GBRDS Food Review",
    page_icon="🍽️",
    layout="centered"
)

st.markdown("""
<style>
/* Blue background */
.stApp {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    background-attachment: fixed;
}
.main .block-container {
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    padding: 2rem;
    margin-top: 1rem;
    margin-bottom: 1rem;
}

/* Button styling */
button {font-size: 24px !important; padding: 20px !important; text-align:center; border-radius: 10px !important; border: 2px solid !important; font-weight: bold !important;}
h1 {font-size: 44px;}
h2, h3 {font-size: 30px;}
p, div {font-size: 20px;}

/* Color-coded rating buttons */
button[key*="rate_0"] {
    background-color: #4CAF50 !important;
    color: white !important;
    border-color: #45a049 !important;
}
button[key*="rate_0"]:hover {
    background-color: #45a049 !important;
}

button[key*="rate_1"] {
    background-color: #FFC107 !important;
    color: black !important;
    border-color: #FFA000 !important;
}
button[key*="rate_1"]:hover {
    background-color: #FFA000 !important;
}

button[key*="rate_2"] {
    background-color: #F44336 !important;
    color: white !important;
    border-color: #da190b !important;
}
button[key*="rate_2"]:hover {
    background-color: #da190b !important;
}
</style>
""", unsafe_allow_html=True)

st.title("GBRDS Food Review")

init_db()

# ---------- RATING BUTTONS ----------
st.subheader("🍽️ How was your food? / మీ ఆహారం ఎలా ఉంది?")

if "rating" not in st.session_state:
    st.session_state.rating = None

ratings = [
    {"label_en": "Tasty", "label_te": "రుచికరంగా ఉంది", "color": "green", "emoji": "😋", "value": "tasty"},
    {"label_en": "Okay", "label_te": "సరాసరి", "color": "orange", "emoji": "😐", "value": "okay"},
    {"label_en": "Not Tasty", "label_te": "రుచికాదు", "color": "red", "emoji": "🤢", "value": "not_tasty"}
]

cols = st.columns(3)
for i, r in enumerate(ratings):
    if cols[i].button(f"{r['emoji']}  {r['label_en']}\n{r['label_te']}", key=f"rate_{i}"):
        st.session_state.rating = r["value"]
        st.rerun()

if st.session_state.rating:
    selected = next((r for r in ratings if r["value"] == st.session_state.rating), None)
    if selected:
        st.markdown(f"""
### Your Rating: 
<span style='color:{selected['color']}; font-size:28px'>{selected['emoji']} {selected['label_en']} / {selected['label_te']}</span>
""", unsafe_allow_html=True)

# ---------- VOICE INPUT ----------
st.subheader("🎤 Speak Your Review / మీ సమీక్షను చెప్పండి")

audio = st.audio_input("Press record, speak, then stop / రికార్డ్ నొక్కండి, మాట్లాడండి, ఆపండి")

if audio and st.session_state.rating:
    if "last_audio" not in st.session_state or audio != st.session_state.last_audio:
        st.session_state.last_audio = audio

        with st.spinner("Listening, translating, and saving..."):
            raw = transcribe_audio(audio)
            english = translate(raw, "English")
            telugu = translate(raw, "Telugu")
            ai_review = clean_review(english)

            save_review(st.session_state.rating, english, telugu, ai_review)

        st.success("✅ Review saved! / సమీక్ష సేవ్ చేయబడింది!")
        st.session_state.rating = None
        st.rerun()

# ---------- DELETE ALL ----------
st.divider()
if "confirm_delete_all" not in st.session_state:
    st.session_state.confirm_delete_all = False
if "password_entered" not in st.session_state:
    st.session_state.password_entered = False

if st.button("🗑️ Delete ALL Reviews / అన్ని సమీక్షలను తొలగించండి"):
    st.session_state.confirm_delete_all = True
    st.session_state.password_entered = False

if st.session_state.confirm_delete_all:
    if not st.session_state.password_entered:
        st.warning("⚠️ Password Required / పాస్వర్డ్ అవసరం")
        password = st.text_input("Enter password to delete all reviews / అన్ని సమీక్షలను తొలగించడానికి పాస్వర్డ్ నమోదు చేయండి:", type="password", key="delete_password")
        
        c1, c2 = st.columns(2)
        if c1.button("❌ Cancel / రద్దు చేయండి", key="cancel_delete_all"):
            st.session_state.confirm_delete_all = False
            st.session_state.password_entered = False
            st.rerun()
        if c2.button("✅ Verify / ధృవీకరించండి", key="verify_password"):
            if password == "121212":
                st.session_state.password_entered = True
                st.rerun()
            else:
                st.error("❌ Incorrect password! / తప్పు పాస్వర్డ్!")
    else:
        st.warning("Are you sure you want to delete ALL reviews? / మీరు నిజంగా అన్ని సమీక్షలను తొలగించాలనుకుంటున్నారా?")
        c1, c2 = st.columns(2)
        if c1.button("❌ Cancel / రద్దు చేయండి"):
            st.session_state.confirm_delete_all = False
            st.session_state.password_entered = False
            st.rerun()
        if c2.button("✅ Yes, Delete Everything / అవును, అన్నింటినీ తొలగించండి"):
            delete_all_reviews()
            st.session_state.confirm_delete_all = False
            st.session_state.password_entered = False
            st.success("All reviews deleted. / అన్ని సమీక్షలు తొలగించబడ్డాయి.")
            st.rerun()

# ---------- DASHBOARD ----------
st.divider()
st.subheader("📊 Dashboard / డాష్బోర్డ్")

reviews_data = get_reviews()

if reviews_data:
    # Calculate rating distribution
    rating_counts = {"tasty": 0, "okay": 0, "not_tasty": 0}
    for review in reviews_data:
        rating = review[1]  # rating is at index 1
        if rating in rating_counts:
            rating_counts[rating] += 1
    
    # Display distribution
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "😋 Tasty / రుచికరంగా",
            rating_counts["tasty"],
            delta=None
        )
    
    with col2:
        st.metric(
            "😐 Okay / సరాసరి",
            rating_counts["okay"],
            delta=None
        )
    
    with col3:
        st.metric(
            "🤢 Not Tasty / రుచికాదు",
            rating_counts["not_tasty"],
            delta=None
        )
    
    # Chart
    chart_data = pd.DataFrame({
        "Rating": ["Tasty / రుచికరంగా", "Okay / సరాసరి", "Not Tasty / రుచికాదు"],
        "Count": [rating_counts["tasty"], rating_counts["okay"], rating_counts["not_tasty"]]
    })
    
    st.bar_chart(chart_data.set_index("Rating"))
    
    # Common Issues Analysis
    st.markdown("### 🔍 Common Issues / సాధారణ సమస్యలు")
    
    if st.button("🔄 Analyze Reviews / సమీక్షలను విశ్లేషించండి", key="analyze_btn"):
        with st.spinner("Analyzing reviews for common issues... / సాధారణ సమస్యల కోసం సమీక్షలను విశ్లేషిస్తోంది..."):
            common_issues = analyze_common_issues(reviews_data)
            st.session_state.common_issues = common_issues
            st.rerun()
    
    if "common_issues" in st.session_state:
        st.info(st.session_state.common_issues)
    
    st.divider()

# ---------- SHOW REVIEWS ----------
st.subheader("🗣️ Reviews / సమీక్షలు")

for rid, rating, en, te, review, time in get_reviews():
    selected = next((r for r in ratings if r['value'] == rating), None)
    color = selected['color'] if selected else "black"
    emoji = selected['emoji'] if selected else ""
    st.markdown(f"""
**<span style='color:{color}; font-size:22px'>{emoji} {rating}</span>**  
🕒 *{time}*  

🇺🇸 **English / ఆంగ్లం:** {en}  

🇮🇳 **Telugu / తెలుగు:** {te}
""", unsafe_allow_html=True)

    # ---- Delete single review ----
    key_base = f"del_{rid}"

    if key_base not in st.session_state:
        st.session_state[key_base] = False

    if st.button("🗑️ Delete This Review / ఈ సమీక్షను తొలగించండి", key=f"{key_base}_btn"):
        st.session_state[key_base] = True

    if st.session_state[key_base]:
        st.warning("Are you sure you want to delete this review? / మీరు నిజంగా ఈ సమీక్షను తొలగించాలనుకుంటున్నారా?")
        c1, c2 = st.columns(2)

        if c1.button("❌ Cancel / రద్దు చేయండి", key=f"{key_base}_cancel"):
            st.session_state[key_base] = False
            st.rerun()

        if c2.button("✅ Yes, Delete / అవును, తొలగించండి", key=f"{key_base}_confirm"):
            delete_review(rid)
            st.session_state[key_base] = False
            st.success("Review deleted. / సమీక్ష తొలగించబడింది.")
            st.rerun()

    st.divider()
