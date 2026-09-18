from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path
import sqlite3
from datetime import date, datetime

from database import get_connection, init_db
from algorithms import compare_sorting_algorithms, calculate_project_effort

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

STATUS = {"new", "working", "done"}
PRIORITIES = {"high", "medium", "low"}

def valid_iso_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False

def validate_due_date(value):
    if not value or not valid_iso_date(value):
        return "تاريخ التسليم غير صحيح"
    if value < date.today().isoformat():
        return "لا يمكن إضافة أو تعديل مهمة بتاريخ تسليم قبل اليوم"
    return None

def row_dict(row):
    return dict(row) if row else None

def validate_task_reference(conn, project_id, member_id, parent_id=None):
    member = conn.execute("SELECT 1 FROM members WHERE id=?", (member_id,)).fetchone()
    if not member:
        return "عضو الفريق غير موجود"
    if parent_id is not None:
        parent = conn.execute(
            "SELECT 1 FROM tasks WHERE id=? AND project_id=?", (parent_id, project_id)
        ).fetchone()
        if not parent:
            return "المهمة الرئيسية غير موجودة ضمن هذا المشروع"
    return None

def status_label(value):
    return {"new": "جديد", "working": "قيد العمل", "done": "منتهي"}.get(value, value)

def log(conn, project_id, message, task_id=None):
    conn.execute(
        "INSERT INTO activity_log(project_id, task_id, message) VALUES (?,?,?)",
        (project_id, task_id, message)
    )

def get_tasks(conn, project_id):
    rows = conn.execute("""
        SELECT t.*, m.name AS member_name, m.short_name
        FROM tasks t
        JOIN members m ON m.id=t.member_id
        WHERE t.project_id=?
        ORDER BY t.id
    """, (project_id,)).fetchall()
    return [dict(r) for r in rows]

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/api/members")
def members():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM members ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/members")
def create_member():
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    short_name = str(data.get("short_name", "")).strip()
    if not name or not short_name:
        return jsonify(error="اسم العضو والاختصار مطلوبان"), 400
    if len(name) > 100 or len(short_name) > 10:
        return jsonify(error="اسم العضو أو الاختصار طويل جدًا"), 400
    conn = get_connection()
    duplicate = conn.execute("SELECT 1 FROM members WHERE name=?", (name,)).fetchone()
    if duplicate:
        conn.close()
        return jsonify(error="هذا العضو موجود مسبقًا"), 409
    cur = conn.execute("INSERT INTO members(name, short_name) VALUES (?, ?)", (name, short_name))
    member_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201

@app.put("/api/members/<int:member_id>")
def update_member(member_id):
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    short_name = str(data.get("short_name", "")).strip()
    if not name or not short_name:
        return jsonify(error="اسم العضو والاختصار مطلوبان"), 400
    if len(name) > 100 or len(short_name) > 10:
        return jsonify(error="اسم العضو أو الاختصار طويل جدًا"), 400
    conn = get_connection()
    member = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    if not member:
        conn.close()
        return jsonify(error="العضو غير موجود"), 404
    duplicate = conn.execute("SELECT 1 FROM members WHERE name=? AND id<>?", (name, member_id)).fetchone()
    if duplicate:
        conn.close()
        return jsonify(error="هذا الاسم مستخدم لعضو آخر"), 409
    conn.execute("UPDATE members SET name=?, short_name=? WHERE id=?", (name, short_name, member_id))
    conn.commit()
    row = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    conn.close()
    return jsonify(dict(row))

@app.delete("/api/members/<int:member_id>")
def delete_member(member_id):
    conn = get_connection()
    member = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    if not member:
        conn.close()
        return jsonify(error="العضو غير موجود"), 404
    assigned = conn.execute("SELECT COUNT(*) FROM tasks WHERE member_id=?", (member_id,)).fetchone()[0]
    if assigned:
        conn.close()
        return jsonify(error="لا يمكن حذف العضو لأنه مكلّف بمهام. غيّر توزيع مهامه أولًا."), 409
    conn.execute("DELETE FROM members WHERE id=?", (member_id,))
    conn.commit()
    conn.close()
    return jsonify(message="تم حذف العضو")

@app.get("/api/projects")
def projects():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.delete("/api/projects/<int:project_id>")
def delete_project(project_id):
    conn = get_connection()
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify(error="المشروع غير موجود"), 404
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return jsonify(message="تم حذف المشروع")

@app.put("/api/projects/<int:project_id>")
def update_project(project_id):
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    if not name or not start_date or not end_date:
        return jsonify(error="اسم المشروع وتواريخه مطلوبة"), 400
    if not valid_iso_date(start_date) or not valid_iso_date(end_date):
        return jsonify(error="تواريخ المشروع غير صحيحة"), 400
    if end_date < start_date:
        return jsonify(error="تاريخ نهاية المشروع يجب أن يكون بعد أو مساويًا لتاريخ البداية"), 400
    conn = get_connection()
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify(error="المشروع غير موجود"), 404
    duplicate = conn.execute("SELECT 1 FROM projects WHERE name=? AND id<>?", (name, project_id)).fetchone()
    if duplicate:
        conn.close()
        return jsonify(error="يوجد مشروع آخر بهذا الاسم"), 409
    conn.execute(
        "UPDATE projects SET name=?, description=?, start_date=?, end_date=? WHERE id=?",
        (name, data.get("description", ""), start_date, end_date, project_id)
    )
    log(conn, project_id, f'تم تعديل المشروع إلى "{name}"')
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return jsonify(dict(row))

@app.post("/api/projects")
def create_project():
    data = request.get_json(force=True)
    required = ["name", "start_date", "end_date"]
    if any(not data.get(k) for k in required):
        return jsonify(error="الحقول الأساسية للمشروع مطلوبة"), 400
    if not valid_iso_date(data["start_date"]) or not valid_iso_date(data["end_date"]):
        return jsonify(error="تواريخ المشروع غير صحيحة"), 400
    if data["end_date"] < data["start_date"]:
        return jsonify(error="تاريخ نهاية المشروع يجب أن يكون بعد أو مساويًا لتاريخ البداية"), 400
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO projects(name,description,start_date,end_date) VALUES (?,?,?,?)",
        (data["name"], data.get("description",""), data["start_date"], data["end_date"])
    )
    project_id = cur.lastrowid
    log(conn, project_id, f'تم إنشاء المشروع "{data["name"]}"')
    conn.commit(); conn.close()
    return jsonify({"id": project_id}), 201

@app.get("/api/projects/<int:project_id>/tasks")
def tasks(project_id):
    conn = get_connection()
    exists = conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone()
    if not exists:
        conn.close()
        return jsonify(error="المشروع غير موجود"), 404
    result = get_tasks(conn, project_id)
    conn.close()
    return jsonify(result)

@app.post("/api/projects/<int:project_id>/tasks")
def create_task(project_id):
    data = request.get_json(force=True)
    if not data.get("title") or data.get("priority") not in PRIORITIES or data.get("status","new") not in STATUS:
        return jsonify(error="بيانات المهمة غير صحيحة"), 400
    due_error = validate_due_date(data.get("due_date"))
    if due_error:
        return jsonify(error=due_error), 400
    try:
        member_id = int(data["member_id"])
        hours = float(data.get("hours", 0))
        if hours < 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(error="عضو الفريق أو الجهد غير صحيح"), 400
    conn = get_connection()
    if not conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
        conn.close()
        return jsonify(error="المشروع غير موجود"), 404
    reference_error = validate_task_reference(conn, project_id, member_id, data.get("parent_id"))
    if reference_error:
        conn.close()
        return jsonify(error=reference_error), 400
    cur = conn.execute("""INSERT INTO tasks
        (project_id,parent_id,title,description,priority,due_date,status,member_id,hours)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (project_id, data.get("parent_id"), data["title"], data.get("description",""),
         data["priority"], data["due_date"], data.get("status","new"),
         member_id, hours)
    )
    task_id = cur.lastrowid
    log(conn, project_id, f'تم إضافة المهمة "{data["title"]}"', task_id)
    conn.commit()
    task = row_dict(conn.execute("""SELECT t.*,m.name member_name,m.short_name
                                    FROM tasks t JOIN members m ON m.id=t.member_id
                                    WHERE t.id=?""",(task_id,)).fetchone())
    conn.close()
    return jsonify(task), 201

@app.put("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(force=True)
    conn = get_connection()
    old = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not old:
        conn.close(); return jsonify(error="المهمة غير موجودة"), 404
    old = dict(old)
    try:
        fields = {
            "title": data.get("title", old["title"]),
            "description": data.get("description", old["description"]),
            "priority": data.get("priority", old["priority"]),
            "due_date": data.get("due_date", old["due_date"]),
            "status": data.get("status", old["status"]),
            "member_id": int(data.get("member_id", old["member_id"])),
            "hours": float(data.get("hours", old["hours"])),
            "parent_id": data.get("parent_id", old["parent_id"])
        }
    except (TypeError, ValueError):
        conn.close()
        return jsonify(error="عضو الفريق أو الجهد غير صحيح"), 400
    if fields["parent_id"] is not None:
        try:
            fields["parent_id"] = int(fields["parent_id"])
        except (TypeError, ValueError):
            conn.close()
            return jsonify(error="المهمة الرئيسية غير صحيحة"), 400
    if fields["priority"] not in PRIORITIES or fields["status"] not in STATUS:
        conn.close(); return jsonify(error="بيانات المهمة غير صحيحة"), 400
    due_error = validate_due_date(fields["due_date"])
    if due_error:
        conn.close(); return jsonify(error=due_error), 400
    if fields["hours"] < 0:
        conn.close(); return jsonify(error="الجهد لا يمكن أن يكون سالبًا"), 400
    reference_error = validate_task_reference(conn, old["project_id"], fields["member_id"], fields["parent_id"])
    if reference_error:
        conn.close(); return jsonify(error=reference_error), 400
    if fields["parent_id"] == task_id:
        conn.close(); return jsonify(error="لا يمكن جعل المهمة أبًا لنفسها"), 400
    conn.execute("""UPDATE tasks SET title=?,description=?,priority=?,due_date=?,status=?,
                    member_id=?,hours=?,parent_id=? WHERE id=?""",
                 (fields["title"],fields["description"],fields["priority"],fields["due_date"],
                  fields["status"],fields["member_id"],fields["hours"],fields["parent_id"],task_id))
    if old["status"] != fields["status"]:
        log(conn, old["project_id"],
            f'تم تغيير حالة "{old["title"]}" من {status_label(old["status"])} إلى {status_label(fields["status"])}', task_id)
    else:
        log(conn, old["project_id"], f'تم تعديل المهمة "{fields["title"]}"', task_id)
    conn.commit()
    task = row_dict(conn.execute("""SELECT t.*,m.name member_name,m.short_name
                                    FROM tasks t JOIN members m ON m.id=t.member_id
                                    WHERE t.id=?""",(task_id,)).fetchone())
    conn.close()
    return jsonify(task)

@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    conn = get_connection()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        conn.close(); return jsonify(error="المهمة غير موجودة"), 404
    task = dict(task)
    log(conn, task["project_id"], f'تم حذف المهمة "{task["title"]}"', task_id)
    conn.execute("DELETE FROM tasks WHERE id=? OR parent_id=?", (task_id, task_id))
    conn.commit(); conn.close()
    return jsonify(ok=True)

@app.post("/api/tasks/<int:parent_id>/subtasks")
def create_subtask(parent_id):
    conn = get_connection()
    parent = conn.execute("SELECT * FROM tasks WHERE id=?", (parent_id,)).fetchone()
    if not parent:
        conn.close(); return jsonify(error="المهمة الرئيسية غير موجودة"), 404
    parent = dict(parent)
    data = request.get_json(force=True)
    if not data.get("title"):
        conn.close(); return jsonify(error="عنوان المهمة الفرعية مطلوب"), 400
    due_date = data.get("due_date", parent["due_date"])
    due_error = validate_due_date(due_date)
    if due_error:
        conn.close(); return jsonify(error=due_error), 400
    try:
        member_id = int(data.get("member_id", parent["member_id"]))
        hours = float(data.get("hours", 0))
        if hours < 0:
            raise ValueError
    except (TypeError, ValueError):
        conn.close(); return jsonify(error="عضو الفريق أو الجهد غير صحيح"), 400
    priority = data.get("priority", parent["priority"])
    status = data.get("status", parent["status"])
    if priority not in PRIORITIES or status not in STATUS:
        conn.close(); return jsonify(error="بيانات المهمة الفرعية غير صحيحة"), 400
    cur = conn.execute("""INSERT INTO tasks
        (project_id,parent_id,title,description,priority,due_date,status,member_id,hours)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (parent["project_id"], parent_id, data["title"], data.get("description",""),
         priority, due_date, status, member_id, hours))
    task_id = cur.lastrowid
    log(conn, parent["project_id"], f'تمت إضافة المهمة الفرعية "{data["title"]}"', task_id)
    conn.commit()
    task = row_dict(conn.execute("""SELECT t.*,m.name member_name,m.short_name
                                    FROM tasks t JOIN members m ON m.id=t.member_id
                                    WHERE t.id=?""",(task_id,)).fetchone())
    conn.close()
    return jsonify(task), 201

@app.get("/api/projects/<int:project_id>/activity")
def activity(project_id):
    conn = get_connection()
    rows = conn.execute("""SELECT message,created_at FROM activity_log
                           WHERE project_id=? ORDER BY id DESC LIMIT 50""",(project_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.delete("/api/projects/<int:project_id>/activity")
def clear_activity(project_id):
    conn = get_connection()
    conn.execute("DELETE FROM activity_log WHERE project_id=?", (project_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "تم تنظيف سجل التغييرات"})

@app.get("/api/projects/<int:project_id>/report")
def report(project_id):
    conn = get_connection()
    all_tasks = get_tasks(conn, project_id)
    done = sum(1 for t in all_tasks if t["status"] == "done")
    pct = round(done / len(all_tasks) * 100) if all_tasks else 0
    member_report = []
    for m in conn.execute("SELECT * FROM members ORDER BY id").fetchall():
        mine = [t for t in all_tasks if t["member_id"] == m["id"]]
        mdone = sum(1 for t in mine if t["status"] == "done")
        member_report.append({**dict(m), "total":len(mine), "done":mdone,
                              "percent":round(mdone / len(mine) * 100) if mine else 0})
    conn.close()
    return jsonify({"percent":pct,"total":len(all_tasks),"done":done,"members":member_report})

@app.get("/api/projects/<int:project_id>/effort")
def effort(project_id):
    conn = get_connection()
    tasks = get_tasks(conn, project_id)
    total = calculate_project_effort(tasks)
    conn.close()
    return jsonify({"total_hours": total})

@app.get("/api/projects/<int:project_id>/sort")
def sorting(project_id):
    key = request.args.get("key","priority")
    if key not in {"priority","due_date"}:
        return jsonify(error="مفتاح ترتيب غير صحيح"), 400
    conn = get_connection()
    if not conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
        conn.close()
        return jsonify(error="المشروع غير موجود"), 404
    tasks = [dict(r) for r in conn.execute(
        "SELECT * FROM tasks WHERE project_id=? ORDER BY id",
        (project_id,)).fetchall()]
    conn.close()
    result = compare_sorting_algorithms(tasks, key)
    merge_ms = result["merge"]["time_ms"]
    quick_ms = result["quick"]["time_ms"]
    if merge_ms < quick_ms:
        result["comparison"] = "في هذه التجربة كان Merge Sort أسرع حسب زمن التنفيذ المقاس."
    elif quick_ms < merge_ms:
        result["comparison"] = "في هذه التجربة كان Quick Sort أسرع حسب زمن التنفيذ المقاس."
    else:
        result["comparison"] = "في هذه التجربة كان الزمن متساويًا تقريبًا بين الخوارزميتين."
    return jsonify(result)

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
else:
    init_db()
