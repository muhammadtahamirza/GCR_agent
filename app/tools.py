from googleapiclient.discovery import build

class ClassroomTools:
    def __init__(self, creds):
        # We store the credentials when we create the class
        self.creds = creds

    def get_courses(self) -> str:
        """Fetches a list of Google Classroom courses the user is enrolled in. Returns course names and their IDs."""
        print("[TOOL EXECUTING] get_courses() called by Gemini...", flush=True)
        service = build("classroom", "v1", credentials=self.creds)
        print("[TOOL] Hitting Google Classroom API for courses...", flush=True)
        results = service.courses().list(pageSize=10).execute()
        courses = results.get("courses", [])

        if not courses:
            print("[TOOL] No courses found.", flush=True)
            return "You are not enrolled in any courses."

        print(f"[TOOL] Successfully fetched {len(courses)} courses.", flush=True)
        response = "Courses:\n"
        for course in courses:
            response += f"- {course['name']} (ID: {course['id']})\n"
        return response

    def get_assignments(self, course_id: str) -> str:
        """Fetches a list of coursework/assignments for a specific Google Classroom course ID."""
        print(f"[TOOL EXECUTING] get_assignments(course_id='{course_id}') called by Gemini...", flush=True)
        service = build("classroom", "v1", credentials=self.creds)
        try:
            print(f"[TOOL] Hitting Google Classroom API for assignments for course {course_id}...", flush=True)
            results = service.courses().courseWork().list(courseId=course_id, pageSize=10).execute()
            coursework = results.get("courseWork", [])

            if not coursework:
                print("[TOOL] No assignments found.", flush=True)
                return "No assignments found for this course."

            print(f"[TOOL] Successfully fetched {len(coursework)} assignments.", flush=True)
            response = "Assignments:\n"
            for work in coursework:
                response += f"- {work['title']} (Due: {work.get('dueDate', 'No due date')})\n"
            return response
        except Exception as e:
            print(f"[TOOL ERROR] {str(e)}", flush=True)
            return f"Error fetching assignments: {str(e)}"

    def get_announcements(self, course_id: str) -> str:
        """Fetches a list of announcements for a specific Google Classroom course ID."""
        print(f"[TOOL EXECUTING] get_announcements(course_id='{course_id}') called by Gemini...", flush=True)
        service = build("classroom", "v1", credentials=self.creds)
        try:
            results = service.courses().announcements().list(courseId=course_id, pageSize=10).execute()
            announcements = results.get("announcements", [])

            if not announcements:
                return "No announcements found for this course."

            response = "Announcements:\n"
            for ann in announcements:
                response += f"- {ann.get('text', 'No text')} (Updated: {ann.get('updateTime', '')})\n"
            return response
        except Exception as e:
            print(f"[TOOL ERROR] {str(e)}", flush=True)
            return f"Error fetching announcements: {str(e)}"

    def get_student_submissions(self, course_id: str, coursework_id: str) -> str:
        """Fetches student submissions for a specific assignment (coursework_id) in a course."""
        print(f"[TOOL EXECUTING] get_student_submissions(course_id='{course_id}', coursework_id='{coursework_id}') called by Gemini...", flush=True)
        service = build("classroom", "v1", credentials=self.creds)
        try:
            results = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=coursework_id
            ).execute()
            submissions = results.get("studentSubmissions", [])

            if not submissions:
                return "No submissions found for this assignment."

            response = "Submissions:\n"
            for sub in submissions:
                state = sub.get('state', 'UNKNOWN')
                grade = sub.get('assignedGrade', 'Not graded')
                response += f"- Submission ID {sub['id']}: State = {state}, Grade = {grade}\n"
            return response
        except Exception as e:
            print(f"[TOOL ERROR] {str(e)}", flush=True)
            return f"Error fetching submissions: {str(e)}"

    def get_students(self, course_id: str) -> str:
        """Fetches the list of students in a course. Returns their names and user IDs."""
        print(f"[TOOL EXECUTING] get_students(course_id='{course_id}') called by Gemini...", flush=True)
        service = build("classroom", "v1", credentials=self.creds)
        try:
            results = service.courses().students().list(courseId=course_id, pageSize=50).execute()
            students = results.get("students", [])

            if not students:
                return "No students found in this course."

            response = "Students:\n"
            for student in students:
                profile = student.get("profile", {})
                name = profile.get("name", {}).get("fullName", "Unknown")
                user_id = student.get("userId")
                response += f"- {name} (User ID: {user_id})\n"
            return response
        except Exception as e:
            print(f"[TOOL ERROR] {str(e)}", flush=True)
            return f"Error fetching students: {str(e)}"

    def create_announcement(self, course_id: str, text: str) -> str:
        """Creates and publishes a new announcement in a specific course."""
        print(f"[TOOL EXECUTING] create_announcement(course_id='{course_id}') called by Gemini...", flush=True)
        service = build("classroom", "v1", credentials=self.creds)
        try:
            announcement = {
                'text': text,
                'state': 'PUBLISHED'
            }
            result = service.courses().announcements().create(
                courseId=course_id,
                body=announcement
            ).execute()
            return f"Successfully created announcement! ID: {result.get('id')}"
        except Exception as e:
            print(f"[TOOL ERROR] {str(e)}", flush=True)
            return f"Error creating announcement: {str(e)}"