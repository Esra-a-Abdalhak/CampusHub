import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "task_manager.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        short_name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        parent_id INTEGER,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
        due_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('new','working','done')),
        member_id INTEGER NOT NULL,
        hours REAL NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY(parent_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY(member_id) REFERENCES members(id)
    );

    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        task_id INTEGER,
        message TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
    );
    """)

    if conn.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO members(name, short_name) VALUES (?, ?)",
            [
                ("أحمد سالم", "أس"),
                ("خالد نورة", "خن"),
                ("محمد مراد", "مم"),
                ("سارة علي", "سع"),
                ("أنس أحمد", "أن"),
            ],
        )

    if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
        cur = conn.execute(
            "INSERT INTO projects(name, description, start_date, end_date) VALUES (?,?,?,?)",
            ("مشروع الخوارزميات", "مشروع إدارة المهام والخوارزميات", "2026-09-01", "2026-09-30"),
        )
        project_id = cur.lastrowid
        seed_tasks = [
            (None,"حساب جهد المشروع (فرق تسد)","حساب إجمالي ساعات المشروع باستخدام الدالة العودية.","medium","2026-09-12","new",3,6),
            (None,"اختبار النظام","اختبار جميع وظائف لوحة كانبان.","medium","2026-09-27","new",2,3),
            (None,"تحليل وتصميم النظام","تحديد المتطلبات وتصميم بنية لوحة كانبان.","high","2026-09-18","working",1,8),
            (None,"تنفيذ خوارزميات الترتيب","ترتيب المهام حسب الأولوية والتاريخ باستخدام Quick Sort و Merge Sort.","high","2026-09-18","working",4,12),
            (None,"تقرير الإنجاز","عرض نسبة الإنجاز وتوزيع المهام المنجزة.","low","2026-09-25","done",2,4),
            (None,"كتابة وثيقة المتطلبات","توثيق متطلبات المستخدم.","high","2026-09-08","done",1,3),
            (None,"تصميم قاعدة البيانات","تصميم جداول المشاريع والمهام.","medium","2026-09-20","done",4,4),
            (None,"تنفيذ Merge Sort","ترتيب المهام بالدمج.","high","2026-09-10","done",4,5),
            (None,"تنفيذ Quick Sort","ترتيب المهام السريع.","high","2026-09-17","done",3,5),
        ]
        ids = []
        for row in seed_tasks:
            cur = conn.execute("""INSERT INTO tasks
                (project_id,parent_id,title,description,priority,due_date,status,member_id,hours)
                VALUES (?,?,?,?,?,?,?,?,?)""", (project_id, *row))
            ids.append(cur.lastrowid)

        # Two real child tasks for the "اختبار النظام" node.
        parent_id = ids[1]
        conn.execute("""INSERT INTO tasks
            (project_id,parent_id,title,description,priority,due_date,status,member_id,hours)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (project_id,parent_id,"اختبار الإضافة","مهمة فرعية","medium","2026-09-27","new",2,1))
        conn.execute("""INSERT INTO tasks
            (project_id,parent_id,title,description,priority,due_date,status,member_id,hours)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (project_id,parent_id,"اختبار التحديث","مهمة فرعية","medium","2026-09-27","new",2,2))

        conn.execute(
            "INSERT INTO activity_log(project_id,message) VALUES (?,?)",
            (project_id, "تم إنشاء المشروع وتجهيز لوحة المهام"),
        )

    conn.commit()
    conn.close()
