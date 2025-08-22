import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import re
import requests

# Backend API URLs
TRAIN_URL = "http://57.255.238.178:5000/train"
QUERY_URL = "http://57.255.238.178:5000/query"

# OCR function to extract text from images
def ocr_from_image(image):
    return pytesseract.image_to_string(image)

# OCR function for multi-page PDFs
def ocr_from_pdf(pdf_bytes):
    images = convert_from_bytes(pdf_bytes)
    text_pages = [ocr_from_image(image) for image in images]
    return "\n".join(text_pages)

# Function to split questions from text
def split_student_answers(text):
    # This regex detects question numbering styles including:
    # 1. or 1) or Q1) or Question 1), etc.
    pattern = re.compile(r'(?=\b(?:Q(?:uestion)?[-\s]*\d+|[0-9]+[\.\)]))', re.IGNORECASE)
    
    # Split text but keep the delimiter with each answer
    parts = pattern.split(text)
    # Clean empty or whitespace-only parts
    parts = [p.strip() for p in parts if p.strip()]
    
    return parts


def split_questions(text):
    # Regex patterns to detect question numbers like 1., 2), Q-1, Question-1)
    pattern = r'(?:(?:^|\n)(?:Q(?:uestion)?[-\s]?|Question\s*|Q\s*|)(\d+)[\.\)]\s*)'
    splits = re.split(pattern, text)
    questions = []
    # re.split returns text chunks and separators, so process accordingly
    if len(splits) <= 1:
        # No question pattern found, treat entire text as one question
        return [text.strip()]
    else:
        # Merge question number with its text
        for i in range(1, len(splits), 2):
            qnum = splits[i]
            qtext = splits[i+1].strip() if i+1 < len(splits) else ""
            questions.append(f"{qnum}. {qtext}")
    return questions

# Function to send question text to backend query API and get model answers
def get_model_answer(question_text):
    payload = {"text": question_text}
    try:
        response = requests.post(QUERY_URL, json=payload)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            # Combine top results texts as model answer
            model_answer = "\n\n".join([r["text"] for r in results])
            return model_answer
        else:
            return "Error fetching model answer."
    except Exception as e:
        return f"Exception: {e}"

# Function to score student answer by comparing with model answer (simple similarity)
def score_answer(model_answer, student_answer):
    # Very simple scoring: proportion of common words (can be improved)
    model_words = set(model_answer.lower().split())
    student_words = set(student_answer.lower().split())
    if not model_words:
        return 0
    common = model_words.intersection(student_words)
    score = len(common) / len(model_words) * 100
    return round(score, 2)

def group_answers(answers, n_groups):
    if n_groups <= 0:
        return []

    avg = len(answers) / n_groups
    grouped = []
    for i in range(n_groups):
        start = int(round(i * avg))
        end = int(round((i + 1) * avg))
        group_text = " ".join(answers[start:end])
        grouped.append(group_text.strip())
    return grouped

def main():
    st.title("AI Exam Grader")

    st.header("Step 1: Upload Question Paper (PDF or Images)")
    question_paper = st.file_uploader("Upload Question Paper", type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)

    if question_paper:
        # Extract text from all pages/images
        question_text = ""
        for file in question_paper:
            file_bytes = file.read()
            if file.type == "application/pdf":
                question_text += ocr_from_pdf(file_bytes) + "\n"
            else:
                image = Image.open(io.BytesIO(file_bytes))
                question_text += ocr_from_image(image) + "\n"
        st.subheader("Extracted Questions Text")
        st.text_area("Questions Text", question_text, height=300)

        # Split questions
        questions = split_questions(question_text)
        st.write(f"Detected {len(questions)} questions.")

        st.header("Step 2: Upload Student Answer Script (PDF or Images)")
        answer_script = st.file_uploader("Upload Student Answer Script", type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True, key="answers")

        if answer_script:
            # Extract student answers text
            student_text = ""
            for file in answer_script:
                file_bytes = file.read()
                if file.type == "application/pdf":
                    student_text += ocr_from_pdf(file_bytes) + "\n"
                else:
                    image = Image.open(io.BytesIO(file_bytes))
                    student_text += ocr_from_image(image) + "\n"
            st.subheader("Extracted Student Answers Text")
            st.text_area("Student Answers Text", student_text, height=300)

            # Split student answers by similar method
            #student_answers = split_questions(student_text)
            # Split student answers by similar method
            student_answers = split_student_answers(student_text)
            #st.write(f"Detected {len(student_answers)} student answers.")
            #st.text_area("Raw student answers OCR text", student_text, height=300)
            #st.write("Split student answers:", student_answers)

            # Show warning only if mismatch BEFORE grouping
            if len(questions) != len(student_answers):
                #st.warning(f"Number of student answers ({len(student_answers)}) doesn't match number of questions ({len(questions)}). Matching as best as possible.")
                student_answers = group_answers(student_answers, len(questions))
            
            #st.write(f"After grouping, student answers count: {len(student_answers)}")
            st.write(f"Detected student's  {len(student_answers)} answers after processing.")
            #st.text_area("Raw student answers OCR text", student_text, height=300)
            #st.write("Split student answers:", student_answers)
            # Align number of answers with questions
            n = min(len(questions), len(student_answers))       
                            
                      
            
            
            #student_answers = split_student_answers(student_text)
            #st.write(f"Detected {len(student_answers)} student answers.")

            #st.text_area("Raw student answers OCR text", student_text, height=300)
            #st.write("Split student answers:", student_answers)

            # Align number of answers with questions best effort
            #n = min(len(questions), len(student_answers))
            #if len(questions) != len(student_answers):
            #    st.warning(f"Number of student answers ({len(student_answers)}) doesn't match number of questions ({len(questions)}). Matching as best as possible.")
             #   student_answers = group_answers(student_answers, len(questions))
             #   st.write(f"After grouping, student answers count: {len(student_answers)}")

            # For each question, get model answer, compare and score
            scores = []
            for i in range(n):
                q = questions[i]
                st.markdown(f"### Question {i+1}")
                st.write(q)

                model_answer = get_model_answer(q)
                st.markdown("**Model Answer:**")
                st.write(model_answer)

                student_answer = student_answers[i]
                st.markdown("**Student Answer:**")
                st.write(student_answer)

                score = score_answer(model_answer, student_answer)
                scores.append(score)
                st.markdown(f"**Score:** {score} / 100")

            # Final grading
            if scores:
                total_score = sum(scores)
                max_score = 100 * len(scores)
                grade_percent = round((total_score / max_score) * 100, 2)
                st.success(f"Final Score: {total_score} / {max_score} ({grade_percent}%)")

if __name__ == "__main__":
    main()

