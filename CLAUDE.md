# Quiz Results Server - תיעוד פרויקט

## מה הפרויקט עושה
שרת Flask המקבל ומאחסן תוצאות מבחנים אמריקאיים שניתנים לתלמידים כקבצי HTML.
התלמידים ממלאים את המבחן ולוחצים שלח → השרת מאחסן את התשובות והציון ב-SQLite.

## טכנולוגיות
- Python + Flask
- SQLite (קובץ מקומי, נשמר ב-/data על Render)
- flask-cors (CORS פתוח לכל המקורות)
- gunicorn (שרת ייצור)

## דיפלויימנט
- פלטפורמה: Render (Free tier)
- URL חי: https://quiz-results.onrender.com
- GitHub repo: https://github.com/yedidyaf/quiz-results
- branch: main
- הערה: השרת נרדם אחרי 15 דק חוסר פעילות, הבקשה הראשונה לוקחת ~50 שניות

## מבנה קבצים
```
quiz_project/
├── app.py           # השרת הראשי
├── requirements.txt # flask, flask-cors, gunicorn
├── render.yaml      # הגדרות דיפלוי + persistent disk ב-/data
└── CLAUDE.md        # קובץ זה
```

## מסד נתונים
טבלה אחת: `results`
```sql
CREATE TABLE results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT NOT NULL,
    exam_id      TEXT NOT NULL,
    answers      TEXT NOT NULL,  -- JSON string
    score        REAL NOT NULL,
    submitted_at TEXT NOT NULL   -- ISO datetime
);
```

## API

### POST /results
קולט תוצאת מבחן.

**Request:**
```json
{
  "student_name": "ישראל ישראלי",
  "exam_id": "math-101",
  "answers": {"q1": "A", "q2": "C", "q3": "B"},
  "score": 85
}
```

**Response 201:**
```json
{
  "id": 1,
  "message": "Result saved"
}
```

**שגיאות:**
- 400 - חסר שדה חובה

---

### GET /results
מחזיר דף HTML עם טבלה של כל התוצאות, ממוין מהחדש לישן.

---

### GET /results/<exam_id>
מחזיר דף HTML עם טבלה מסוננת לפי מבחן ספציפי.
כולל לינק "View all exams" לחזרה לכל התוצאות.

---

## איך תלמיד שולח מהHTML
```javascript
fetch("https://quiz-results.onrender.com/results", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    student_name: "שם התלמיד",
    exam_id: "math-101",
    answers: { q1: "A", q2: "C" },
    score: 85
  })
});
```

## רעיונות להמשך
- GET /results/student/<student_name> - תוצאות לפי תלמיד
- GET /results/<exam_id>/stats - ממוצע, מקסימום, מינימום לפי מבחן
- GET /export/<exam_id> - ייצוא ל-CSV
- אימות פשוט עם API key כדי שרק אתה תוכל לראות תוצאות
- דף HTML יפה יותר לתוצאות
