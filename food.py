import streamlit as st
import sqlite3
import os
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

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

# ---------- UI ----------
st.set_page_config(
    page_title="Food Review 🍔",
    page_icon="🍽️",
    layout="centered"
)

st.markdown("""
<style>
button {font-size: 24px !important; padding: 20px !important; text-align:center;}
h1 {font-size: 44px;}
h2, h3 {font-size: 30px;}
p, div {font-size: 20px;}
</style>
""", unsafe_allow_html=True)

st.title("🍔 Food Review")

st.info(
    "🍴 Choose how tasty the food is.\n\n"
    "🎤 Speak your review in **any language**.\n\n"
    "✅ When recording stops, the review is **automatically saved**.\n\n"
    "🌍 Reviews are translated into **English & Telugu** and polished by AI."
)

init_db()

# ---------- RATING BUTTONS ----------
st.subheader("🍽️ How was your food?")

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
st.subheader("🎤 Speak Your Review")

audio = st.audio_input("Press record, speak, then stop")

if audio and st.session_state.rating:
    if "last_audio" not in st.session_state or audio != st.session_state.last_audio:
        st.session_state.last_audio = audio

        with st.spinner("Listening, translating, and saving..."):
            raw = transcribe_audio(audio)
            english = translate(raw, "English")
            telugu = translate(raw, "Telugu")
            ai_review = clean_review(english)

            save_review(st.session_state.rating, english, telugu, ai_review)

        st.success("✅ Review saved!")
        st.session_state.rating = None
        st.rerun()

# ---------- DELETE ALL ----------
st.divider()
if "confirm_delete_all" not in st.session_state:
    st.session_state.confirm_delete_all = False

if st.button("🗑️ Delete ALL Reviews"):
    st.session_state.confirm_delete_all = True

if st.session_state.confirm_delete_all:
    st.warning("Are you sure you want to delete ALL reviews?")
    c1, c2 = st.columns(2)
    if c1.button("❌ Cancel"):
        st.session_state.confirm_delete_all = False
        st.rerun()
    if c2.button("✅ Yes, Delete Everything"):
        delete_all_reviews()
        st.session_state.confirm_delete_all = False
        st.success("All reviews deleted.")
        st.rerun()

# ---------- SHOW REVIEWS ----------
st.subheader("🗣️ Reviews")

for rid, rating, en, te, review, time in get_reviews():
    selected = next((r for r in ratings if r['value'] == rating), None)
    color = selected['color'] if selected else "black"
    emoji = selected['emoji'] if selected else ""
    st.markdown(f"""
**<span style='color:{color}; font-size:22px'>{emoji} {rating}</span>**  
🕒 *{time}*  

🇺🇸 **English:** {en}  

🇮🇳 **Telugu:** {te}  

🤖 **AI Review:** {review}
""", unsafe_allow_html=True)

    # ---- Delete single review ----
    key_base = f"del_{rid}"

    if key_base not in st.session_state:
        st.session_state[key_base] = False

    if st.button("🗑️ Delete This Review", key=f"{key_base}_btn"):
        st.session_state[key_base] = True

    if st.session_state[key_base]:
        st.warning("Are you sure you want to delete this review?")
        c1, c2 = st.columns(2)

        if c1.button("❌ Cancel", key=f"{key_base}_cancel"):
            st.session_state[key_base] = False
            st.rerun()

        if c2.button("✅ Yes, Delete", key=f"{key_base}_confirm"):
            delete_review(rid)
            st.session_state[key_base] = False
            st.success("Review deleted.")
            st.rerun()

    st.divider()
