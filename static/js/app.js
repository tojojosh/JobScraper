/**
 * UK Skilled Jobs Portal – Frontend Application
 */

// ── State ────────────────────────────────────────────────────────
const state = {
  page: 1,
  pageSize: 50,
  search: '',
  dateFrom: '',
  dateTo: '',
  sortBy: 'scrape_date',
  sortOrder: 'desc',
  source: '',
  totalJobs: 0,
  totalPages: 0,
};

// ── DOM refs ─────────────────────────────────────────────────────
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  dateFrom:       $('#dateFrom'),
  dateTo:         $('#dateTo'),
  search:         $('#searchInput'),
  source:         $('#sourceFilter'),
  btnApply:       $('#btnApplyFilters'),
  btnReset:       $('#btnResetFilters'),
  btnExportCSV:   $('#btnExportCSV'),
  btnExportExcel: $('#btnExportExcel'),
  btnExportJSON:  $('#btnExportJSON'),
  btnScrapeNow:   $('#btnScrapeNow'),
  btnToggleTheme: $('#btnToggleTheme'),
  tbody:          $('#jobsBody'),
  loading:        $('#loadingOverlay'),
  pageInfo:       $('#paginationInfo'),
  pageNav:        $('#paginationNav'),
  pageSize:       $('#pageSizeSelect'),
  lastRunBadge:   $('#lastRunBadge'),
  // Stats
  statTotal:      $('#statTotal'),
  statCompanies:  $('#statCompanies'),
  statDateRange:  $('#statDateRange'),
  statSources:    $('#statSources'),
  // Modals – JSON export
  jsonDateInput:  $('#jsonDateInput'),
  jsonDateList:   $('#jsonDateList'),
  jsonRangeFrom:  $('#jsonRangeFrom'),
  jsonRangeTo:    $('#jsonRangeTo'),
  jsonTabSingle:  $('#jsonTabSingle'),
  jsonTabRange:   $('#jsonTabRange'),
  btnDownloadJSON:$('#btnDownloadJSON'),
  scrapeBody:     $('#scrapeModalBody'),
};

// ── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setDefaultDates();
  bindEvents();
  loadJobs();
  loadStats();
  loadScrapeStatus();
  restoreTheme();
});

function setDefaultDates() {
  const today = new Date();
  const weekAgo = new Date(today);
  weekAgo.setDate(today.getDate() - 7);
  dom.dateTo.value   = fmt(today);
  dom.dateFrom.value = fmt(weekAgo);
  state.dateTo   = dom.dateTo.value;
  state.dateFrom = dom.dateFrom.value;
}

function fmt(d) {
  return d.toISOString().slice(0, 10);
}

// ── Events ───────────────────────────────────────────────────────
function bindEvents() {
  dom.btnApply.addEventListener('click', applyFilters);
  dom.btnReset.addEventListener('click', resetFilters);
  dom.btnExportCSV.addEventListener('click',   (e) => { e.preventDefault(); exportData('csv'); });
  dom.btnExportExcel.addEventListener('click', (e) => { e.preventDefault(); exportData('excel'); });
  dom.btnExportJSON.addEventListener('click',  (e) => { e.preventDefault(); openJSONModal(); });
  dom.btnDownloadJSON.addEventListener('click', downloadDailyJSON);
  dom.btnScrapeNow.addEventListener('click', triggerScrape);
  dom.btnToggleTheme.addEventListener('click', toggleTheme);

  dom.pageSize.addEventListener('change', () => {
    state.pageSize = parseInt(dom.pageSize.value, 10);
    state.page = 1;
    loadJobs();
  });

  // Enter key in search
  dom.search.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') applyFilters();
  });

  // Sortable columns
  $$('.sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (state.sortBy === col) {
        state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortBy = col;
        state.sortOrder = 'asc';
      }
      updateSortIndicators();
      state.page = 1;
      loadJobs();
    });
  });
}

function applyFilters() {
  state.dateFrom = dom.dateFrom.value;
  state.dateTo   = dom.dateTo.value;
  state.search   = dom.search.value.trim();
  state.source   = dom.source.value;
  state.page     = 1;
  loadJobs();
  loadStats();
}

function resetFilters() {
  setDefaultDates();
  dom.search.value = '';
  dom.source.value = '';
  state.search = '';
  state.source = '';
  state.sortBy = 'scrape_date';
  state.sortOrder = 'desc';
  state.page = 1;
  updateSortIndicators();
  loadJobs();
  loadStats();
}

// ── Fetch Jobs ───────────────────────────────────────────────────
async function loadJobs() {
  showLoading(true);

  const params = new URLSearchParams({
    page:       state.page,
    page_size:  state.pageSize,
    date_from:  state.dateFrom,
    date_to:    state.dateTo,
    search:     state.search,
    source:     state.source,
    sort_by:    state.sortBy,
    sort_order: state.sortOrder,
  });

  try {
    const res  = await fetch(`/api/jobs?${params}`);
    const data = await res.json();

    state.totalJobs  = data.total;
    state.totalPages = data.total_pages;

    renderTable(data.jobs, data.page, data.page_size);
    renderPagination(data);
  } catch (err) {
    console.error('Failed to load jobs:', err);
    dom.tbody.innerHTML =
      '<tr><td colspan="11" class="text-center text-danger py-4">Failed to load jobs.</td></tr>';
  } finally {
    showLoading(false);
  }
}

// ── Render Table ─────────────────────────────────────────────────
function renderTable(jobs, page, pageSize) {
  if (!jobs.length) {
    dom.tbody.innerHTML =
      '<tr><td colspan="11" class="text-center text-muted py-5">' +
      '<i class="bi bi-inbox fs-1 d-block mb-2"></i>No jobs found for the selected filters.' +
      '</td></tr>';
    return;
  }

  const startIdx = (page - 1) * pageSize;

  dom.tbody.innerHTML = jobs.map((job, i) => `
    <tr>
      <td class="text-center text-muted">${startIdx + i + 1}</td>
      <td class="fw-semibold text-truncate-cell" title="${esc(job.company)}">${esc(job.company)}</td>
      <td class="text-truncate-cell" title="${esc(job.title)}">${esc(job.title)}</td>
      <td>
        <a href="${esc(job.url)}" target="_blank" rel="noopener" class="job-link">
          View <i class="bi bi-box-arrow-up-right"></i>
        </a>
      </td>
      <td>${esc(job.location)}</td>
      <td class="text-nowrap">${job.salary ? `<span class="salary-badge">${esc(job.salary)}</span>` : '<span class="text-muted">–</span>'}</td>
      <td class="text-muted">${esc(job.category || '–')}</td>
      <td class="text-muted">${esc(job.experience_level || '–')}</td>
      <td class="text-muted">${esc(job.job_type || '–')}</td>
      <td><small>${job.scrape_date}</small></td>
      <td><span class="source-badge ${job.source}">${esc(job.source)}</span></td>
    </tr>
  `).join('');
}

// ── Pagination ───────────────────────────────────────────────────
function renderPagination(data) {
  const { page, total_pages, total, page_size } = data;
  const from = total ? (page - 1) * page_size + 1 : 0;
  const to   = Math.min(page * page_size, total);

  dom.pageInfo.textContent = `Showing ${from}–${to} of ${total.toLocaleString()} jobs`;

  if (total_pages <= 1) {
    dom.pageNav.innerHTML = '';
    return;
  }

  let pages = [];
  const delta = 2;
  const left  = Math.max(1, page - delta);
  const right = Math.min(total_pages, page + delta);

  // Previous
  pages.push(pageItem('&laquo;', page - 1, page === 1));

  if (left > 1) {
    pages.push(pageItem('1', 1));
    if (left > 2) pages.push(pageItem('…', null, true));
  }

  for (let p = left; p <= right; p++) {
    pages.push(pageItem(p, p, false, p === page));
  }

  if (right < total_pages) {
    if (right < total_pages - 1) pages.push(pageItem('…', null, true));
    pages.push(pageItem(total_pages, total_pages));
  }

  // Next
  pages.push(pageItem('&raquo;', page + 1, page === total_pages));

  dom.pageNav.innerHTML = pages.join('');

  // Bind click
  dom.pageNav.querySelectorAll('.page-link[data-page]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      state.page = parseInt(el.dataset.page, 10);
      loadJobs();
    });
  });
}

function pageItem(label, page, disabled = false, active = false) {
  const cls = `page-item${disabled ? ' disabled' : ''}${active ? ' active' : ''}`;
  const attr = page && !disabled ? `data-page="${page}" href="#"` : '';
  return `<li class="${cls}"><a class="page-link" ${attr}>${label}</a></li>`;
}

// ── Stats ────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const params = new URLSearchParams({
      date_from: state.dateFrom,
      date_to:   state.dateTo,
    });
    const res  = await fetch(`/api/stats?${params}`);
    const data = await res.json();

    dom.statTotal.textContent     = (data.total_jobs || 0).toLocaleString();
    dom.statCompanies.textContent = (data.unique_companies || 0).toLocaleString();
    dom.statDateRange.textContent = `${data.date_range.from} → ${data.date_range.to}`;

    const srcCount = Object.keys(data.sources || {}).length;
    dom.statSources.textContent = `${srcCount} active`;
  } catch (err) {
    console.error('Stats load error:', err);
  }
}

// ── Last Scrape Status ───────────────────────────────────────────
async function loadScrapeStatus() {
  try {
    const res  = await fetch('/api/scrape/status');
    const data = await res.json();
    if (data.status && data.status !== 'no_runs') {
      dom.lastRunBadge.classList.remove('d-none');
      const badge = data.status === 'completed' ? 'bg-success' : 'bg-danger';
      dom.lastRunBadge.className = `badge ${badge}`;
      dom.lastRunBadge.textContent = `Last: ${data.date} (${data.new_jobs || 0} new)`;
    }
  } catch (_) { /* silent */ }
}

// ── Export ────────────────────────────────────────────────────────
function exportData(type) {
  const params = new URLSearchParams({
    date_from:  state.dateFrom,
    date_to:    state.dateTo,
    search:     state.search,
    source:     state.source,
    sort_by:    state.sortBy,
    sort_order: state.sortOrder,
  });

  const url = type === 'csv'
    ? `/api/jobs/export/csv?${params}`
    : `/api/jobs/export/excel?${params}`;

  window.location.href = url;
  showToast('Export started', `Your ${type.toUpperCase()} file is downloading.`);
}

// ── JSON Export (single date or date range) ─────────────────────
async function openJSONModal() {
  const modal = new bootstrap.Modal($('#jsonDateModal'));
  dom.jsonDateInput.value = fmt(new Date());

  // Pre-fill range inputs with the current table filter dates
  dom.jsonRangeFrom.value = state.dateFrom || fmt((() => { const d = new Date(); d.setDate(d.getDate() - 7); return d; })());
  dom.jsonRangeTo.value   = state.dateTo   || fmt(new Date());

  // Load available dates for single-date tab
  try {
    const res  = await fetch('/api/dates');
    const data = await res.json();
    if (data.dates && data.dates.length) {
      dom.jsonDateList.innerHTML =
        '<p class="text-muted small mb-2">Available dates:</p>' +
        data.dates.slice(0, 14).map((d) =>
          `<a href="#" class="badge bg-primary-subtle text-primary me-1 mb-1 json-date-link" data-date="${d.date}">${d.date} (${d.count})</a>`
        ).join('');

      dom.jsonDateList.querySelectorAll('.json-date-link').forEach((el) => {
        el.addEventListener('click', (e) => {
          e.preventDefault();
          dom.jsonDateInput.value = el.dataset.date;
        });
      });
    } else {
      dom.jsonDateList.innerHTML = '<p class="text-muted small">No data yet.</p>';
    }
  } catch (_) {
    dom.jsonDateList.innerHTML = '';
  }

  modal.show();
}

function downloadDailyJSON() {
  // Determine which tab is active
  const rangeTabActive = dom.jsonTabRange.classList.contains('active');

  if (rangeTabActive) {
    // ── Date range mode ──
    const from = dom.jsonRangeFrom.value;
    const to   = dom.jsonRangeTo.value;

    if (!from || !to) {
      showToast('Error', 'Please select both From and To dates.', 'danger');
      return;
    }
    if (from > to) {
      showToast('Error', 'From date must be before or equal to To date.', 'danger');
      return;
    }

    window.location.href = `/api/jobs/export/json?date_from=${from}&date_to=${to}`;
    bootstrap.Modal.getInstance($('#jsonDateModal')).hide();
    showToast('Download started', `JSON for ${from} to ${to} is downloading.`);
  } else {
    // ── Single date mode ──
    const d = dom.jsonDateInput.value;
    if (!d) {
      showToast('Error', 'Please select a date.', 'danger');
      return;
    }
    window.location.href = `/api/jobs/daily-json/${d}`;
    bootstrap.Modal.getInstance($('#jsonDateModal')).hide();
    showToast('Download started', `JSON for ${d} is downloading.`);
  }
}

// ── Trigger Scrape ───────────────────────────────────────────────
async function triggerScrape() {
  const modal = new bootstrap.Modal($('#scrapeModal'));
  dom.scrapeBody.innerHTML =
    '<div class="spinner-border text-primary mb-3" role="status"></div>' +
    '<p>Scraping in progress… this may take several minutes.</p>';
  modal.show();

  try {
    const res  = await fetch('/api/scrape', { method: 'POST' });
    const data = await res.json();

    if (data.status === 'completed') {
      dom.scrapeBody.innerHTML =
        '<i class="bi bi-check-circle-fill text-success fs-1 mb-3 d-block"></i>' +
        `<p class="mb-1"><strong>${data.new_jobs}</strong> new jobs stored.</p>` +
        `<p class="text-muted">${data.jobs_found} found, ${data.duplicates} duplicates removed.</p>`;
      loadJobs();
      loadStats();
      loadScrapeStatus();
    } else {
      dom.scrapeBody.innerHTML =
        '<i class="bi bi-exclamation-triangle-fill text-danger fs-1 mb-3 d-block"></i>' +
        `<p>Scrape failed: ${data.error || 'Unknown error'}</p>`;
    }
  } catch (err) {
    dom.scrapeBody.innerHTML =
      '<i class="bi bi-exclamation-triangle-fill text-danger fs-1 mb-3 d-block"></i>' +
      `<p>Request failed: ${err.message}</p>`;
  }
}

// ── Sort Indicators ──────────────────────────────────────────────
function updateSortIndicators() {
  $$('.sortable').forEach((th) => {
    th.classList.remove('asc', 'desc');
    if (th.dataset.sort === state.sortBy) {
      th.classList.add(state.sortOrder);
    }
  });
}

// ── Theme Toggle ─────────────────────────────────────────────────
function toggleTheme() {
  const html = document.documentElement;
  const dark = html.getAttribute('data-bs-theme') === 'dark';
  html.setAttribute('data-bs-theme', dark ? 'light' : 'dark');
  localStorage.setItem('theme', dark ? 'light' : 'dark');
  dom.btnToggleTheme.innerHTML = dark
    ? '<i class="bi bi-moon-stars-fill"></i>'
    : '<i class="bi bi-sun-fill"></i>';
}

function restoreTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark') {
    document.documentElement.setAttribute('data-bs-theme', 'dark');
    dom.btnToggleTheme.innerHTML = '<i class="bi bi-sun-fill"></i>';
  }
}

// ── Helpers ──────────────────────────────────────────────────────
function showLoading(show) {
  dom.loading.classList.toggle('d-none', !show);
}

function showToast(title, body, variant = 'primary') {
  const toast = $('#appToast');
  $('#toastTitle').textContent = title;
  $('#toastBody').textContent  = body;
  toast.classList.remove('text-bg-primary', 'text-bg-success', 'text-bg-danger');
  toast.classList.add(`text-bg-${variant}`);
  bootstrap.Toast.getOrCreateInstance(toast).show();
}

function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
