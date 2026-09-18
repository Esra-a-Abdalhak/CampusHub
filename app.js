(() => {
  let projects = [], members = [], tasks = [], activity = [], currentProject = null;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const priorityText = {high:"عالية", medium:"متوسطة", low:"منخفضة"};
  const statusText = {new:"جديد", working:"قيد العمل", done:"منتهي"};
  const nextStatus = {new:"working", working:"done", done:"new"};

  async function api(url, options = {}) {
    const res = await fetch(url, {headers:{"Content-Type":"application/json"}, ...options});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "حدث خطأ في الخادم");
    return data;
  }

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2400);
  }

  function todayISO() {
    const d = new Date();
    const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  }

  async function load() {
    [projects, members] = await Promise.all([api("/api/projects"), api("/api/members")]);
    currentProject = projects.some(p => p.id === currentProject) ? currentProject : projects[0]?.id;
    if (currentProject) await refresh();
    else renderAll();
  }

  async function refresh() {
    if (!currentProject) return;
    [tasks, activity] = await Promise.all([
      api(`/api/projects/${currentProject}/tasks`),
      api(`/api/projects/${currentProject}/activity`)
    ]);
    renderAll();
  }

  function member(id) {
    return members.find(m => m.id == id) || {name:"—", short_name:"—"};
  }

  function renderMembers() {
    const count = $("#memberCount");
    const list = $("#membersList");
    if (!count || !list) return;
    count.textContent = `${members.length} عضو`;
    list.innerHTML = members.length ? members.map(m => `
      <div class="member-management-row">
        <span class="member-avatar large">${esc(m.short_name)}</span>
        <div class="member-management-info"><strong>${esc(m.name)}</strong><small>عضو رقم ${m.id}</small></div>
        <div class="member-management-actions">
          <button type="button" class="member-edit-btn" data-member-action="edit" data-mid="${m.id}">تعديل</button>
          <button type="button" class="member-delete-btn" data-member-action="delete" data-mid="${m.id}">حذف</button>
        </div>
      </div>`).join("") : `<div class="empty-state">لا يوجد أعضاء مسجلون.</div>`;
    document.querySelectorAll('[data-member-action="edit"]').forEach(btn => btn.onclick = () => openMemberModal(+btn.dataset.mid));
    document.querySelectorAll('[data-member-action="delete"]').forEach(btn => btn.onclick = () => deleteMemberById(+btn.dataset.mid));
  }

  function renderProjects() {
    const countEl = $("#projectCount");
    if (countEl) countEl.textContent = projects.length;
    $("#projectList").innerHTML = projects.map(p => {
      return `<div class="project-item ${p.id === currentProject ? "active" : ""}" data-pid="${p.id}">
        <i></i><span class="project-name">${esc(p.name)}</span>
        <div class="project-item-actions">
          <button class="project-edit-btn" type="button" data-project-action="edit" data-pid="${p.id}" title="تعديل المشروع">تعديل</button>
          <button class="project-delete-btn" type="button" data-project-action="delete" data-pid="${p.id}" title="حذف المشروع">حذف</button>
        </div>
      </div>`;
    }).join("");
    document.querySelectorAll(".project-item").forEach(x => x.onclick = async (e) => {
      if (e.target.closest("[data-project-action]")) return;
      currentProject = +x.dataset.pid;
      await refresh();
    });
    document.querySelectorAll("[data-project-action=edit]").forEach(btn => btn.onclick = (e) => {
      e.stopPropagation();
      openProjectModal(+btn.dataset.pid);
    });
    document.querySelectorAll("[data-project-action=delete]").forEach(btn => btn.onclick = async (e) => {
      e.stopPropagation();
      await deleteProjectById(+btn.dataset.pid);
    });
  }

  function taskCard(t) {
    const m = member(t.member_id);
    const subs = tasks.filter(x => x.parent_id === t.id);
    return `<article class="task-card" draggable="true" data-id="${t.id}">
      <div class="task-top">
        <span class="priority ${t.priority}">${priorityText[t.priority]}</span>
        <button class="status-btn" data-next data-id="${t.id}">→ ${statusText[nextStatus[t.status]]}</button>
      </div>
      <h4>${esc(t.title)}</h4>
      <p>${esc(t.description)}</p>
      <div class="task-meta">
        <span>تسليم: ${esc(t.due_date)}</span>
        <span class="member"><span class="member-avatar">${esc(m.short_name)}</span>${esc(m.name)}</span>
      </div>
      <div class="hours">الجهد المتوقع: ${Number(t.hours) || 0} ساعة</div>
      ${subs.length ? `<div class="subtasks">
        <div class="subtasks-title">المهام الفرعية</div>
        ${subs.map(s => `<div class="subtask"><span>↳ ${esc(s.title)}</span><span>${Number(s.hours)||0} س</span></div>`).join("")}
      </div>` : ""}
      <div class="task-actions">
        <button class="link-btn" data-action="sub" data-id="${t.id}">+ مهمة فرعية</button>
        <button class="link-btn" data-action="edit" data-id="${t.id}">تعديل</button>
        <button class="link-btn delete" data-action="delete" data-id="${t.id}">حذف</button>
      </div>
    </article>`;
  }

  function renderBoard() {
    const groups = {new:[], working:[], done:[]};
    tasks.filter(t => !t.parent_id).forEach(t => groups[t.status]?.push(t));
    const columns = [
      ["new", "جديد", "new-dot"],
      ["working", "قيد العمل", "work-dot"],
      ["done", "منتهي", "done-dot"]
    ];

    $("#kanban").innerHTML = columns.map(([status, title, dot]) => `
      <section class="column">
        <div class="column-head">
          <span class="dot ${dot}"></span><h3>${title}</h3><small>${groups[status].length}</small>
        </div>
        <div class="task-stack" data-drop="${status}">${groups[status].map(taskCard).join("")}</div>
        <button class="add-column" data-add-status="${status}">+ إضافة مهمة في ${title}</button>
      </section>`).join("");

    document.querySelectorAll(".task-card").forEach(card => {
      card.ondragstart = e => {
        card.classList.add("dragging");
        e.dataTransfer.setData("text/plain", card.dataset.id);
      };
      card.ondragend = () => card.classList.remove("dragging");
    });

    document.querySelectorAll("[data-drop]").forEach(zone => {
      zone.ondragover = e => e.preventDefault();
      zone.ondrop = async e => {
        e.preventDefault();
        const id = +e.dataTransfer.getData("text/plain");
        const t = tasks.find(x => x.id === id);
        if (t && t.status !== zone.dataset.drop) await updateTask(t, {status:zone.dataset.drop});
      };
    });

    document.querySelectorAll("[data-next]").forEach(b => b.onclick = () => cycleStatus(+b.dataset.id));
    document.querySelectorAll("[data-action]").forEach(b => b.onclick = () => taskAction(b.dataset.action, +b.dataset.id));
    document.querySelectorAll("[data-add-status]").forEach(b => b.onclick = () => openTaskModal(null, b.dataset.addStatus));
  }

  async function runSorting() {
    try {
      const key = $("#sortKey").value;
      const data = await api(`/api/projects/${currentProject}/sort?key=${encodeURIComponent(key)}`);
      const merge = data.merge || {items:[], ms:0};
      const quick = data.quick || {items:[], ms:0};
      const renderList = (items) => items.length
        ? items.map(t => `<li>${esc(t.title)}</li>`).join("")
        : `<li class="sort-placeholder">لا توجد مهام رئيسية لترتيبها.</li>`;
      $("#mergeTime").textContent = `${Number(merge.time_ms ?? merge.ms ?? 0).toFixed(4)} ms`;
      $("#quickTime").textContent = `${Number(quick.time_ms ?? quick.ms ?? 0).toFixed(4)} ms`;
      $("#mergeList").innerHTML = renderList(merge.items || []);
      $("#quickList").innerHTML = renderList(quick.items || []);
      $("#sortComparison").textContent = data.comparison || "تمت المقارنة حسب الزمن المقاس.";
      toast("تم تنفيذ Merge Sort وQuick Sort ومقارنة الزمن");
    } catch (e) { toast(e.message); }
  }

  function renderActivity() {
    $("#activityLog").innerHTML = activity.length
      ? activity.map(a => `<div class="activity-item"><span class="activity-dot"></span><span>${esc(a.message)}</span><span class="activity-time">${esc(a.created_at)}</span></div>`).join("")
      : `<div class="empty-state">لا توجد تغييرات مسجلة بعد.</div>`;
  }

  async function clearActivity() {
    if (!activity.length) {
      toast("سجل التغييرات فارغ بالفعل");
      return;
    }
    if (!confirm("هل تريد تنظيف سجل تغييرات الحالة بالكامل؟")) return;
    try {
      await api(`/api/projects/${currentProject}/activity`, {method:"DELETE"});
      await refresh();
      toast("تم تنظيف سجل التغييرات");
    } catch (e) {
      toast(e.message);
    }
  }

  async function updateTask(t, patch) {
    try {
      await api(`/api/tasks/${t.id}`, {method:"PUT", body:JSON.stringify({...t, ...patch})});
      await refresh();
      toast("تم تحديث المهمة");
    } catch (e) {
      toast(e.message);
    }
  }

  async function cycleStatus(id) {
    const t = tasks.find(x => x.id === id);
    if (!t) return;
    const states = ["new", "working", "done"];
    const next = states[(states.indexOf(t.status) + 1) % states.length];
    await updateTask(t, {status:next});
  }

  async function taskAction(action, id) {
    const t = tasks.find(x => x.id === id);
    if (!t) return;
    if (action === "delete") {
      if (confirm("حذف المهمة؟ سيتم حذف مهامها الفرعية أيضًا.")) {
        try {
          await api(`/api/tasks/${id}`, {method:"DELETE"});
          await refresh();
          toast("تم حذف المهمة");
        } catch (e) { toast(e.message); }
      }
    } else if (action === "edit") {
      openTaskModal(t);
    } else {
      openSubtaskModal(t);
    }
  }

  function openModal(content) {
    $("#modal").innerHTML = content;
    $("#modalBackdrop").classList.remove("hidden");
    document.querySelectorAll(".close").forEach(b => b.onclick = closeModal);
  }

  function closeModal() {
    $("#modalBackdrop").classList.add("hidden");
    $("#modal").innerHTML = "";
  }

  $("#modalBackdrop").onclick = e => {
    if (e.target.id === "modalBackdrop") closeModal();
  };

  function openMemberModal(memberId = null) {
    const edit = !!memberId;
    const current = edit ? members.find(m => m.id === memberId) : null;
    if (edit && !current) return;
    openModal(`<div class="modal-head"><h2>${edit ? "تعديل العضو" : "إضافة عضو جديد"}</h2><button class="close">×</button></div>
      <form id="memberForm">
        <div class="form-grid">
          <div class="field full"><label>اسم العضو</label><input name="name" maxlength="100" placeholder="مثال: ليان محمد" value="${esc(current?.name || "")}" required></div>
          <div class="field full"><label>الاختصار</label><input name="short_name" maxlength="10" placeholder="مثال: لم" value="${esc(current?.short_name || "")}" required></div>
        </div>
        <div class="modal-actions"><button class="primary-btn">${edit ? "حفظ التعديل" : "إضافة العضو"}</button><button type="button" class="ghost-btn close">إلغاء</button></div>
      </form>`);

    $("#memberForm").onsubmit = async e => {
      e.preventDefault();
      try {
        const f = Object.fromEntries(new FormData(e.target));
        if (edit) {
          const updated = await api(`/api/members/${memberId}`, {method:"PUT", body:JSON.stringify(f)});
          const index = members.findIndex(m => m.id === memberId);
          if (index !== -1) members[index] = updated;
          closeModal();
          renderMembers();
          if (currentProject) await refresh();
          toast(`تم تعديل العضو ${updated.name}`);
        } else {
          const m = await api("/api/members", {method:"POST", body:JSON.stringify(f)});
          members.push(m);
          renderMembers();
          closeModal();
          toast(`تمت إضافة العضو ${m.name}`);
        }
      } catch (err) { toast(err.message); }
    };
  }

  async function deleteMemberById(memberId) {
    const m = members.find(x => x.id === memberId);
    if (!m) return;
    if (!confirm(`هل أنت متأكد من حذف العضو "${m.name}"؟`)) return;
    try {
      await api(`/api/members/${memberId}`, {method:"DELETE"});
      members = members.filter(x => x.id !== memberId);
      renderMembers();
      if (currentProject) await refresh();
      toast("تم حذف العضو");
    } catch (err) { toast(err.message); }
  }

  async function deleteProjectById(projectId) {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;
    const confirmed = confirm(`هل أنت متأكد من حذف المشروع "${project.name}"؟\nسيتم حذف جميع مهامه وسجل نشاطه نهائيًا.`);
    if (!confirmed) return;
    try {
      await api(`/api/projects/${projectId}`, {method:"DELETE"});
      projects = projects.filter(p => p.id !== projectId);
      if (currentProject === projectId) {
        currentProject = projects[0]?.id || null;
        tasks = [];
        activity = [];
      }
      renderProjects();
      if (currentProject) await refresh();
      else renderAll();
      toast("تم حذف المشروع");
    } catch (err) { toast(err.message); }
  }

  async function deleteCurrentProject() {
    if (currentProject) await deleteProjectById(currentProject);
  }

  function openProjectModal(projectId = null) {
    const edit = !!projectId;
    const project = edit ? projects.find(p => p.id === projectId) : null;
    if (edit && !project) return;
    const today = todayISO();
    const start = project?.start_date || today;
    const end = project?.end_date || "";
    openModal(`<div class="modal-head"><h2>${edit ? "تعديل المشروع" : "إنشاء مشروع"}</h2><button class="close">×</button></div>
      <form id="projectForm">
        <div class="form-grid">
          <div class="field full"><label>اسم المشروع</label><input name="name" required value="${esc(project?.name || "")}"></div>
          <div class="field full"><label>الوصف</label><textarea name="description">${esc(project?.description || "")}</textarea></div>
          <div class="field"><label>تاريخ البداية</label><input type="date" name="start_date" value="${esc(start)}" required></div>
          <div class="field"><label>تاريخ النهاية</label><input type="date" name="end_date" min="${edit ? esc(start) : today}" value="${esc(end)}" required></div>
        </div>
        <div class="modal-actions"><button class="primary-btn">${edit ? "حفظ التعديل" : "إنشاء"}</button><button type="button" class="ghost-btn close">إلغاء</button></div>
      </form>`);

    const form = $("#projectForm");
    const startInput = form.querySelector('[name="start_date"]');
    const endInput = form.querySelector('[name="end_date"]');
    startInput.onchange = () => { endInput.min = startInput.value; };
    form.onsubmit = async e => {
      e.preventDefault();
      try {
        const f = Object.fromEntries(new FormData(e.target));
        if (f.end_date < f.start_date) { toast("تاريخ نهاية المشروع يجب أن يكون بعد أو مساويًا لتاريخ البداية"); return; }
        if (edit) {
          const updated = await api(`/api/projects/${projectId}`, {method:"PUT", body:JSON.stringify(f)});
          const index = projects.findIndex(p => p.id === projectId);
          if (index !== -1) projects[index] = updated;
          closeModal();
          renderProjects();
          if (currentProject === projectId) await refresh();
          toast("تم تعديل المشروع");
        } else {
          const p = await api("/api/projects", {method:"POST", body:JSON.stringify(f)});
          if (!p || !p.id) throw new Error("تعذر إنشاء المشروع");
          currentProject = Number(p.id);
          closeModal();
          await load();
          toast("تم إنشاء المشروع بنجاح");
        }
      } catch (err) { toast(err.message); }
    };
  }

  function openTaskModal(t = null, status = "new") {
    const edit = !!t;
    const today = todayISO();
    const due = t?.due_date || today;
    openModal(`<div class="modal-head"><h2>${edit ? "تعديل المهمة" : "إضافة مهمة"}</h2><button class="close">×</button></div>
      <form id="taskForm">
        <div class="form-grid">
          <div class="field full"><label>عنوان المهمة</label><input name="title" required value="${esc(t?.title || "")}"></div>
          <div class="field full"><label>الوصف</label><textarea name="description">${esc(t?.description || "")}</textarea></div>
          <div class="field"><label>الأولوية</label><select name="priority">${["high","medium","low"].map(x => `<option value="${x}" ${t?.priority===x?"selected":""}>${priorityText[x]}</option>`).join("")}</select></div>
          <div class="field"><label>الحالة</label><select name="status">${["new","working","done"].map(x => `<option value="${x}" ${(t?.status || status)===x?"selected":""}>${statusText[x]}</option>`).join("")}</select></div>
          <div class="field"><label>تاريخ التسليم</label><input type="date" name="due_date" min="${today}" value="${esc(due)}" required><div class="date-hint">لا يمكن اختيار تاريخ قبل اليوم.</div></div>
          <div class="field"><label>الجهد المتوقع (ساعة)</label><input type="number" name="hours" min="0" step="0.5" required value="${Number(t?.hours ?? 4)}"></div>
          <div class="field full"><label>عضو الفريق</label><select name="member_id">${members.map(m => `<option value="${m.id}" ${Number(t?.member_id || 1)===m.id?"selected":""}>${esc(m.name)}</option>`).join("")}</select></div>
        </div>
        <div class="modal-actions"><button class="primary-btn">${edit ? "حفظ" : "إضافة"}</button><button type="button" class="ghost-btn close">إلغاء</button></div>
      </form>`);

    $("#taskForm").onsubmit = async e => {
      e.preventDefault();
      try {
        const v = Object.fromEntries(new FormData(e.target));
        v.hours = +v.hours;
        v.member_id = +v.member_id;
        if (!v.due_date || v.due_date < today) { toast("لا يمكن اختيار تاريخ تسليم قبل اليوم"); return; }
        if (edit) await updateTask(t, v);
        else await api(`/api/projects/${currentProject}/tasks`, {method:"POST", body:JSON.stringify(v)});
        closeModal();
        await refresh();
        toast(edit ? "تم حفظ التعديل" : "تم إضافة المهمة");
      } catch (err) { toast(err.message); }
    };
  }

  function openSubtaskModal(parent) {
    const today = todayISO();
    const due = parent.due_date >= today ? parent.due_date : today;
    openModal(`<div class="modal-head"><h2>إضافة مهمة فرعية</h2><button class="close">×</button></div>
      <p>المهمة الرئيسية: <b>${esc(parent.title)}</b></p>
      <form id="subForm">
        <div class="form-grid">
          <div class="field full"><label>عنوان المهمة الفرعية</label><input name="title" required></div>
          <div class="field full"><label>الوصف</label><textarea name="description"></textarea></div>
          <div class="field"><label>الأولوية</label><select name="priority">${["high","medium","low"].map(x => `<option value="${x}" ${x===parent.priority?"selected":""}>${priorityText[x]}</option>`).join("")}</select></div>
          <div class="field"><label>الحالة</label><select name="status">${["new","working","done"].map(x => `<option value="${x}" ${x===parent.status?"selected":""}>${statusText[x]}</option>`).join("")}</select></div>
          <div class="field"><label>تاريخ التسليم</label><input type="date" name="due_date" min="${today}" value="${esc(due)}" required><div class="date-hint">لا يمكن اختيار تاريخ قبل اليوم.</div></div>
          <div class="field"><label>الجهد المتوقع (ساعة)</label><input name="hours" type="number" min="0" step="0.5" value="2" required></div>
          <div class="field full"><label>عضو الفريق</label><select name="member_id">${members.map(m => `<option value="${m.id}" ${m.id===parent.member_id?"selected":""}>${esc(m.name)}</option>`).join("")}</select></div>
        </div>
        <div class="modal-actions"><button class="primary-btn">إضافة</button><button type="button" class="ghost-btn close">إلغاء</button></div>
      </form>`);

    $("#subForm").onsubmit = async e => {
      e.preventDefault();
      try {
        const f = Object.fromEntries(new FormData(e.target));
        f.hours = +f.hours;
        f.member_id = +f.member_id;
        if (!f.due_date || f.due_date < today) { toast("لا يمكن اختيار تاريخ تسليم قبل اليوم"); return; }
        await api(`/api/tasks/${parent.id}/subtasks`, {method:"POST", body:JSON.stringify(f)});
        closeModal();
        await refresh();
        toast("تمت إضافة المهمة الفرعية");
      } catch (err) { toast(err.message); }
    };
  }


  async function renderEffort() {
    const data = await api(`/api/projects/${currentProject}/effort`);
    $("#effortTotal").textContent = (Number(data.total_hours) || 0) + " ساعة";
    const roots = tasks.filter(t => !t.parent_id);
    function node(t, depth = 0) {
      const children = tasks.filter(x => x.parent_id === t.id);
      return `<div class="tree-node ${depth === 0 ? "root" : ""}">
        <div class="tree-row"><strong>${"↳ ".repeat(depth)}${esc(t.title)}</strong><span class="tree-hours">${Number(t.hours)||0} ساعة</span></div>
        ${children.length ? `<div class="tree-children">${children.map(x => node(x, depth + 1)).join("")}</div>` : ""}
      </div>`;
    }
    $("#effortTree").innerHTML = roots.map(t => node(t)).join("") || `<div class="empty-state">لا توجد مهام لعرض شجرة الجهد.</div>`;
  }

  async function renderReport() {
    const r = await api(`/api/projects/${currentProject}/report`);
    $("#reportPercent").textContent = r.percent + "%";
    $("#memberReport").innerHTML = r.members.map(m => `<div class="member-row">
      <div class="member-name">${esc(m.name)}</div><div class="bar"><i style="width:${m.percent}%"></i></div><div class="member-num">${m.done} منجز / ${m.total}</div>
    </div>`).join("");
  }

  async function renderAll() {
    renderProjects();
    renderMembers();
    renderBoard();
    renderActivity();
    if (currentProject) {
      await renderEffort();
      await renderReport();
    } else {
      $("#effortTotal").textContent = "0 ساعة";
      $("#effortTree").innerHTML = `<div class="empty-state">لا يوجد مشروع حالي.</div>`;
      $("#reportPercent").textContent = "0%";
      $("#memberReport").innerHTML = `<div class="empty-state">لا يوجد مشروع حالي.</div>`;
    }
  }

  document.querySelectorAll(".nav-item").forEach(b => b.onclick = () => {
    document.querySelectorAll(".nav-item").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".page").forEach(x => x.classList.remove("active-page"));
    $("#" + b.dataset.page).classList.add("active-page");
  });

  $("#newProjectBtn").addEventListener("click", () => openProjectModal());
  // فتح نافذة إضافة عضو بشكل مباشر + تفويض للنقر لضمان عمل الزر حتى بعد إعادة رسم الواجهة.
  const newMemberBtn = $("#newMemberBtn");
  if (newMemberBtn) {
    newMemberBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openMemberModal();
    });
  }
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("#newMemberBtn");
    if (btn) {
      e.preventDefault();
      openMemberModal();
    }
  });
  $("#newTaskBtn").onclick = () => openTaskModal();
  $("#clearActivityBtn").onclick = clearActivity;
  $("#sortBtn").onclick = runSorting;
  load().catch(e => { console.error(e); toast(e.message + " — شغّل الخادم أولاً"); });
})();
