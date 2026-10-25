import os
import pandas as pd
import psycopg2
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Student Academic Tracker", page_icon="🎓", layout="wide")
st.title("🎓 Student Academic Tracker")
st.caption("DBMS Mini-Project | PostgreSQL + Streamlit")

def get_conn():
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing settings in .env: " + ", ".join(missing))
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=5
    )

def query_df(sql, params=None):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def execute(sql, params=None, returning=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone() if returning else None
        conn.commit()
        return row

def show_error(e):
    st.error(str(e))
    st.info("Check that PostgreSQL is running and your .env connection settings are correct.")

try:
    # Connection check
    query_df("SELECT 1 AS connected")
except Exception as e:
    st.error("Cannot connect to PostgreSQL yet.")
    st.code("python -m pip install -r requirements.txt")
    st.write("Create a `.env` file using `.env.example` and enter your PostgreSQL password.")
    st.exception(e)
    st.stop()

tabs = st.tabs(["Dashboard & Search", "Add Student", "Academic Records", "Seminars", "Activities", "Gap Years"])

with tabs[0]:
    st.subheader("Find a student")
    search = st.text_input("Search by student name or roll number")
    try:
        if search.strip():
            students = query_df("""
                SELECT student_id, roll_number, full_name, department, admission_year, email
                FROM students
                WHERE full_name ILIKE %s OR roll_number ILIKE %s
                ORDER BY full_name
            """, (f"%{search.strip()}%", f"%{search.strip()}%"))
        else:
            students = query_df("""
                SELECT student_id, roll_number, full_name, department, admission_year, email
                FROM students ORDER BY full_name
            """)
        st.dataframe(students, use_container_width=True, hide_index=True)
        st.metric("Students in database", int(query_df("SELECT COUNT(*) AS n FROM students").iloc[0]["n"]))
    except Exception as e:
        show_error(e)

    st.subheader("Semester progression")
    student_options = query_df("SELECT student_id, full_name, roll_number FROM students ORDER BY full_name")
    if not student_options.empty:
        student_options["label"] = student_options["full_name"] + " (" + student_options["roll_number"] + ")"
        selected_label = st.selectbox("Choose student", student_options["label"].tolist())
        selected_id = int(student_options.loc[student_options["label"] == selected_label, "student_id"].iloc[0])
        sems = query_df("""
            SELECT semester_number, academic_year, sgpa, cgpa, status
            FROM semesters WHERE student_id = %s ORDER BY semester_number
        """, (selected_id,))
        if not sems.empty:
            st.dataframe(sems, use_container_width=True, hide_index=True)
            graph_data = sems.melt(
                id_vars=["semester_number"], value_vars=["sgpa", "cgpa"],
                var_name="Metric", value_name="Score"
            ).dropna()
            if not graph_data.empty:
                fig = px.line(graph_data, x="semester_number", y="Score", color="Metric",
                              markers=True, title="Semester-wise SGPA / CGPA")
                fig.update_xaxes(dtick=1, title="Semester")
                fig.update_yaxes(range=[0, 10], title="Grade Point")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No semester records for this student yet. Add them in Academic Records.")
        gaps = query_df("SELECT start_year, end_year, reason FROM gap_years WHERE student_id=%s ORDER BY start_year", (selected_id,))
        if not gaps.empty:
            st.warning("Academic gap/drop year record found")
            st.dataframe(gaps, use_container_width=True, hide_index=True)
    else:
        st.info("Add a student to begin.")

    with st.expander("Update or delete a student"):
        all_students = query_df("SELECT student_id, roll_number, full_name, department, admission_year, email FROM students ORDER BY full_name")
        if not all_students.empty:
            choice = st.selectbox(
                "Select student to edit",
                all_students["student_id"].tolist(),
                format_func=lambda x: f'{all_students.loc[all_students.student_id == x, "full_name"].iloc[0]} — {all_students.loc[all_students.student_id == x, "roll_number"].iloc[0]}',
                key="edit_student_choice"
            )
            rec = all_students[all_students.student_id == choice].iloc[0]
            with st.form("edit_student_form"):
                new_name = st.text_input("Full name", str(rec["full_name"]))
                new_roll = st.text_input("Roll number", str(rec["roll_number"]))
                new_dept = st.text_input("Department", str(rec["department"]))
                new_year = st.number_input("Admission year", min_value=2000, max_value=2100,
                                           value=int(rec["admission_year"]) if pd.notna(rec["admission_year"]) else 2026)
                new_email = st.text_input("Email (optional)", "" if pd.isna(rec["email"]) else str(rec["email"]))
                save = st.form_submit_button("Save changes")
            if save:
                try:
                    execute("""UPDATE students SET full_name=%s, roll_number=%s, department=%s,
                               admission_year=%s, email=%s WHERE student_id=%s""",
                            (new_name.strip(), new_roll.strip(), new_dept.strip(), new_year,
                             new_email.strip() or None, int(choice)))
                    st.success("Student updated.")
                    st.rerun()
                except Exception as e:
                    show_error(e)
            if st.button("Delete selected student", type="secondary"):
                try:
                    execute("DELETE FROM students WHERE student_id=%s", (int(choice),))
                    st.success("Student and dependent records deleted according to foreign-key rules.")
                    st.rerun()
                except Exception as e:
                    show_error(e)
        else:
            st.caption("No students to edit yet.")

with tabs[1]:
    st.subheader("Add student")
    with st.form("add_student_form", clear_on_submit=True):
        roll = st.text_input("Roll number *")
        name = st.text_input("Full name *")
        dept = st.text_input("Department", value="TE")
        admission_year = st.number_input("Admission year", min_value=2000, max_value=2100, value=2026)
        email = st.text_input("Email (optional)")
        submitted = st.form_submit_button("Add student")
    if submitted:
        if not roll.strip() or not name.strip():
            st.warning("Roll number and full name are required.")
        else:
            try:
                execute("""INSERT INTO students(roll_number, full_name, department, admission_year, email)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (roll.strip(), name.strip(), dept.strip() or "TE", int(admission_year), email.strip() or None))
                st.success("Student added successfully.")
                st.rerun()
            except Exception as e:
                show_error(e)

with tabs[2]:
    st.subheader("Add semester and marks")
    students = query_df("SELECT student_id, full_name, roll_number FROM students ORDER BY full_name")
    if students.empty:
        st.info("Add a student first.")
    else:
        students["label"] = students["full_name"] + " (" + students["roll_number"] + ")"
        with st.form("semester_form"):
            label = st.selectbox("Student", students["label"].tolist(), key="sem_student")
            sem_num = st.number_input("Semester number", min_value=1, max_value=12, value=1)
            academic_year = st.text_input("Academic year", value="2025-2026")
            sgpa = st.number_input("SGPA (0–10)", min_value=0.0, max_value=10.0, value=0.0, step=0.1)
            cgpa = st.number_input("CGPA (0–10)", min_value=0.0, max_value=10.0, value=0.0, step=0.1)
            status = st.selectbox("Status", ["Completed", "Ongoing", "Backlog"])
            sem_submit = st.form_submit_button("Save semester")
        if sem_submit:
            sid = int(students.loc[students["label"] == label, "student_id"].iloc[0])
            try:
                execute("""INSERT INTO semesters(student_id, semester_number, academic_year, sgpa, cgpa, status)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(student_id, semester_number) DO UPDATE SET
                           academic_year=EXCLUDED.academic_year, sgpa=EXCLUDED.sgpa,
                           cgpa=EXCLUDED.cgpa, status=EXCLUDED.status""",
                        (sid, int(sem_num), academic_year.strip(), float(sgpa), float(cgpa), status))
                st.success("Semester saved.")
                st.rerun()
            except Exception as e:
                show_error(e)

    st.markdown("#### Subject catalogue")
    with st.form("subject_form"):
        code = st.text_input("Subject code")
        subject_name = st.text_input("Subject name")
        subject_sem = st.number_input("Subject semester", min_value=1, max_value=12, value=1)
        subject_type = st.selectbox("Type", ["Theory", "Lab"])
        max_marks = st.number_input("Maximum marks", min_value=1.0, value=100.0)
        subject_submit = st.form_submit_button("Add subject")
    if subject_submit:
        try:
            execute("""INSERT INTO subjects(subject_code, subject_name, semester_number, subject_type, maximum_marks)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (code.strip(), subject_name.strip(), int(subject_sem), subject_type, float(max_marks)))
            st.success("Subject added.")
            st.rerun()
        except Exception as e:
            show_error(e)

    subjects = query_df("SELECT subject_id, subject_code, subject_name, semester_number, subject_type, maximum_marks FROM subjects ORDER BY semester_number, subject_type, subject_name")
    if not subjects.empty:
        st.dataframe(subjects, use_container_width=True, hide_index=True)
        sems = query_df("""SELECT s.semester_id, st.full_name, st.roll_number, s.semester_number
                           FROM semesters s JOIN students st ON st.student_id=s.student_id
                           ORDER BY st.full_name, s.semester_number""")
        if not sems.empty:
            sems["label"] = sems["full_name"] + " (" + sems["roll_number"] + ") - Sem " + sems["semester_number"].astype(str)
           
            sems["label"] = (
                sems["full_name"]
                + " ("
                + sems["roll_number"]
                + ") - Sem "
                + sems["semester_number"].astype(str)
            )

            # Keep dropdowns OUTSIDE the form so changes
            # immediately update the marks limit.
            sem_label = st.selectbox(
                "Student semester",
                sems["label"].tolist(),
                key="marks_semester_select"
            )

            selected_sem_num = int(
                sems.loc[
                    sems["label"] == sem_label,
                    "semester_number"
                ].iloc[0]
            )

            eligible_subjects = subjects[
                subjects["semester_number"] == selected_sem_num
            ].copy()

            if eligible_subjects.empty:
                st.warning(
                    "No subjects exist for this semester. "
                    "Add a subject in the Subject Catalogue first."
                )
            else:
                sub_id = st.selectbox(
                    "Subject",
                    eligible_subjects["subject_id"].tolist(),
                    format_func=lambda x: (
                        f'{eligible_subjects.loc[eligible_subjects.subject_id == x, "subject_code"].iloc[0]}'
                        f' — {eligible_subjects.loc[eligible_subjects.subject_id == x, "subject_name"].iloc[0]}'
                    ),
                    key="marks_subject_select"
                )

                max_for_subject = float(
                    eligible_subjects.loc[
                        eligible_subjects["subject_id"] == sub_id,
                        "maximum_marks"
                    ].iloc[0]
                )

                st.caption(
                    f"Maximum marks for this subject: {max_for_subject:g}"
                )

                with st.form("marks_form"):
                    marks = st.number_input(
                        "Marks obtained",
                        min_value=0.0,
                        max_value=max_for_subject,
                        value=0.0,
                        step=1.0,
                        key=f"marks_input_{sub_id}"
                    )

                    marks_submit = st.form_submit_button(
                        "Save marks"
                    )

                if marks_submit:
                    sem_id = int(
                        sems.loc[
                            sems["label"] == sem_label,
                            "semester_id"
                        ].iloc[0]
                    )
                    try:
                        execute(
                            """
                            INSERT INTO student_marks
                            (semester_id, subject_id,
                             marks_obtained, maximum_marks)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (semester_id, subject_id)
                            DO UPDATE SET
                                marks_obtained = EXCLUDED.marks_obtained,
                                maximum_marks = EXCLUDED.maximum_marks
                            """,
                            (
                                sem_id,
                                int(sub_id),
                                float(marks),
                                max_for_subject
                            )
                        )

                        st.success("Marks saved successfully!")
                        st.rerun()

                    except Exception as e:
                        show_error(e)

            if marks_submit:
                sem_id = int(sems.loc[sems["label"] == sem_label, "semester_id"].iloc[0])
                try:
                    execute("""INSERT INTO student_marks(semester_id, subject_id, marks_obtained, maximum_marks)
                               VALUES (%s,%s,%s,%s)
                               ON CONFLICT(semester_id, subject_id) DO UPDATE SET
                               marks_obtained=EXCLUDED.marks_obtained, maximum_marks=EXCLUDED.maximum_marks""",
                            (sem_id, int(sub_id), float(marks), max_for_subject))
                    st.success("Marks saved.")
                    st.rerun()
                except Exception as e:
                    show_error(e)
        marks_df = query_df("""SELECT st.full_name, st.roll_number, se.semester_number,
                              su.subject_code, su.subject_name, su.subject_type,
                              sm.marks_obtained, sm.maximum_marks
                              FROM student_marks sm
                              JOIN semesters se ON se.semester_id=sm.semester_id
                              JOIN students st ON st.student_id=se.student_id
                              JOIN subjects su ON su.subject_id=sm.subject_id
                              ORDER BY st.full_name, se.semester_number, su.subject_name""")
        st.markdown("#### Recorded marks")
        st.dataframe(marks_df, use_container_width=True, hide_index=True)
    else:
        st.info("Add subjects to record theory and lab marks.")

with tabs[3]:
    st.subheader("Seminars")
    students = query_df("SELECT student_id, full_name, roll_number FROM students ORDER BY full_name")
    if students.empty:
        st.info("Add a student first.")
    else:
        students["label"] = students["full_name"] + " (" + students["roll_number"] + ")"
        with st.form("seminar_form", clear_on_submit=True):
            student_label = st.selectbox("Student", students["label"].tolist(), key="seminar_student")
            title = st.text_input("Seminar title")
            seminar_type = st.selectbox("Seminar type", ["Internal", "External"])
            seminar_date = st.date_input("Seminar date")
            certificate = st.text_input("Certificate details (optional)")
            seminar_submit = st.form_submit_button("Add seminar")
        if seminar_submit:
            try:
                sid = int(students.loc[students["label"] == student_label, "student_id"].iloc[0])
                execute("""INSERT INTO seminars(student_id, seminar_title, seminar_type, seminar_date, certificate_details)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (sid, title.strip(), seminar_type, seminar_date, certificate.strip() or None))
                st.success("Seminar added.")
                st.rerun()
            except Exception as e:
                show_error(e)
    st.dataframe(query_df("""SELECT st.full_name, st.roll_number, se.seminar_title, se.seminar_type,
                            se.seminar_date, se.certificate_details
                            FROM seminars se JOIN students st ON st.student_id=se.student_id
                            ORDER BY se.seminar_date DESC NULLS LAST"""), use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Activities")
    students = query_df("SELECT student_id, full_name, roll_number FROM students ORDER BY full_name")
    if students.empty:
        st.info("Add a student first.")
    else:
        students["label"] = students["full_name"] + " (" + students["roll_number"] + ")"
        with st.form("activity_form", clear_on_submit=True):
            student_label = st.selectbox("Student", students["label"].tolist(), key="activity_student")
            activity_name = st.text_input("Activity name")
            activity_type = st.selectbox("Activity type", ["Technical", "Co-curricular", "Extracurricular"])
            activity_date = st.date_input("Activity date")
            achievement = st.text_area("Achievement/details (optional)")
            activity_submit = st.form_submit_button("Add activity")
        if activity_submit:
            try:
                sid = int(students.loc[students["label"] == student_label, "student_id"].iloc[0])
                execute("""INSERT INTO activities(student_id, activity_name, activity_type, activity_date, achievement)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (sid, activity_name.strip(), activity_type, activity_date, achievement.strip() or None))
                st.success("Activity added.")
                st.rerun()
            except Exception as e:
                show_error(e)
    st.dataframe(query_df("""SELECT st.full_name, st.roll_number, a.activity_name, a.activity_type,
                            a.activity_date, a.achievement
                            FROM activities a JOIN students st ON st.student_id=a.student_id
                            ORDER BY a.activity_date DESC NULLS LAST"""), use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader("Academic gap years")
    students = query_df("SELECT student_id, full_name, roll_number FROM students ORDER BY full_name")
    if students.empty:
        st.info("Add a student first.")
    else:
        students["label"] = students["full_name"] + " (" + students["roll_number"] + ")"
        with st.form("gap_form", clear_on_submit=True):
            student_label = st.selectbox("Student", students["label"].tolist(), key="gap_student")
            start_year = st.number_input("Gap start year", min_value=1950, max_value=2100, value=2024)
            end_year = st.number_input("Gap end year", min_value=1950, max_value=2100, value=2024)
            reason = st.text_area("Reason (optional)")
            gap_submit = st.form_submit_button("Add gap year")
        if gap_submit:
            if end_year < start_year:
                st.warning("End year must be the same as or later than start year.")
            else:
                try:
                    sid = int(students.loc[students["label"] == student_label, "student_id"].iloc[0])
                    execute("""INSERT INTO gap_years(student_id, start_year, end_year, reason)
                               VALUES (%s,%s,%s,%s)""",
                            (sid, int(start_year), int(end_year), reason.strip() or None))
                    st.success("Gap year recorded.")
                    st.rerun()
                except Exception as e:
                    show_error(e)
    st.dataframe(query_df("""SELECT st.full_name, st.roll_number, g.start_year, g.end_year, g.reason
                            FROM gap_years g JOIN students st ON st.student_id=g.student_id
                            ORDER BY g.start_year"""), use_container_width=True, hide_index=True)

st.divider()
st.caption("Database changes are logged by PostgreSQL triggers when the optional sync trigger script is installed. Google Sheets sync requires service-account setup and a running sync_worker.py.")
