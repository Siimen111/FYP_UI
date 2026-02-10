const apiBaseInput = document.getElementById('apiBase');
const apiBaseInputAlt = document.getElementById('apiBaseLawyer');
const baseModelInput = document.getElementById('baseModel');
const baseModelInputAlt = document.getElementById('baseModelLawyer');
const openSettingsButton = document.getElementById('openSettings');
const settingsModal = document.getElementById('settingsModal');
const uploaderInput = document.getElementById('uploaderName');
const loginView = document.getElementById('loginView');
const lawyerApp = document.getElementById('lawyerView');
const loginButtons = document.querySelectorAll('[data-login-lawyer]');
const logoutButton = document.getElementById('logoutButton');
const uploadFileInput = document.getElementById('docxFile');
const resetCommitsButton = document.getElementById('resetCommits');
const uploadProgress = document.getElementById('uploadProgress');
const conflictTitle = document.getElementById('conflictTitle');
const conflictList = document.getElementById('conflictList');
const conflictSuggestButton = document.getElementById('runSuggestFromConflict');
const refreshCommitsButton = document.getElementById('refreshCommits');
const refreshCommitsButtonAlt = document.getElementById('uploadStart');
const runMergeButton = document.getElementById('runMerge');
const runMergeButtonAlt = document.getElementById('runMergeLawyer');
const runSuggestButton = document.getElementById('runSuggest');
const runSuggestButtonAlt = document.getElementById('runSuggestLawyer');
const runApplyButton = document.getElementById('runApply');
const runApplyButtonAlt = document.getElementById('runApplyLawyer');
const suggestModeSelect = document.getElementById('suggestMode');
const suggestModeButtons = document.querySelectorAll('[data-suggest-mode]');
const suggestProgress = document.getElementById('suggestProgress');
const suggestProgressAlt = document.getElementById('suggestProgressLawyer');
const commitList = document.getElementById('commitList');
const commitListAlt = document.getElementById('lawyerCommitList');
const commitStatus = document.getElementById('commitStatus');
const commitStatusAlt = document.getElementById('commitStatusLawyer');
const selectionMeta = document.getElementById('selectionMeta');
const mergeResultEl = document.getElementById('mergeResult');
const mergeResultAlt = document.getElementById('mergeResultLawyer');
const suggestResultEl = document.getElementById('suggestResult');
const suggestResultAlt = document.getElementById('suggestResultLawyer');
const suggestActionsEl = document.getElementById('suggestActions');
const suggestActionsAlt = document.getElementById('suggestActionsLawyer');
const applyResultEl = document.getElementById('applyResult');
const applyResultAlt = document.getElementById('applyResultLawyer');
const toast = document.getElementById('toast');
const authorInput = document.getElementById('author');
const authorInputAlt = document.getElementById('authorLawyer');
const messageInput = document.getElementById('message');
const messageInputAlt = document.getElementById('messageLawyer');
const matterNameInput = document.getElementById('matterName');
const viewTabs = document.querySelectorAll('[data-view]');
const consoleView = document.getElementById('consoleView');
const lawyerView = document.getElementById('lawyerView');

let commits = [];
let selectedBase = null;
let selectedLeft = null;
let selectedRight = null;
let mergeResult = null;
let suggestResult = null;
let suggestPhaseTimer = [];
let selectedConflictCommit = null;
let suggestMode = suggestModeSelect?.value || 'full';

const STORAGE_KEYS = {
  apiBase: 'vtrack.apiBase',
  baseModel: 'vtrack.baseModel',
  lawyers: 'vtrack.lawyers',
  activeLawyer: 'vtrack.activeLawyer',
};

const DEFAULTS = {
  apiBase: 'http://127.0.0.1:8000',
  baseModel: 'C:\\Users\\sherm\\FYP\\src\\gemma_3_4b_it',
};

const DEFAULT_LAWYERS = [
  { id: 'lawyer-a', label: 'Lawyer A' },
  { id: 'lawyer-b', label: 'Lawyer B' },
  { id: 'lawyer-c', label: 'Lawyer C' },
];

const buildDefaultLawyers = () =>
  DEFAULT_LAWYERS.reduce((acc, lawyer) => {
    acc[lawyer.id] = {
      id: lawyer.id,
      label: lawyer.label,
      name: lawyer.label,
      uploader: lawyer.label,
      author: lawyer.label,
    };
    return acc;
  }, {});

const loadLawyers = () => {
  let stored = null;
  try {
    stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.lawyers) || 'null');
  } catch (error) {
    stored = null;
  }
  const defaults = buildDefaultLawyers();
  if (!stored || typeof stored !== 'object') {
    localStorage.setItem(STORAGE_KEYS.lawyers, JSON.stringify(defaults));
    return defaults;
  }
  DEFAULT_LAWYERS.forEach(lawyer => {
    if (!stored[lawyer.id]) {
      stored[lawyer.id] = defaults[lawyer.id];
    }
  });
  localStorage.setItem(STORAGE_KEYS.lawyers, JSON.stringify(stored));
  return stored;
};

const saveLawyers = map => {
  localStorage.setItem(STORAGE_KEYS.lawyers, JSON.stringify(map));
};

const shortId = id => (id ? `${id.slice(0, 6)}...${id.slice(-4)}` : '--');

let toastTimer = null;
let lawyers = loadLawyers();
let currentLawyerId =
  localStorage.getItem(STORAGE_KEYS.activeLawyer) || DEFAULT_LAWYERS[0].id;

if (!lawyers[currentLawyerId]) {
  currentLawyerId = DEFAULT_LAWYERS[0].id;
  localStorage.setItem(STORAGE_KEYS.activeLawyer, currentLawyerId);
}

const getCurrentLawyer = () => lawyers[currentLawyerId];

const applyLawyerProfile = () => {
  const profile = getCurrentLawyer();
  if (!profile) {
    return;
  }
  const uploaderName =
    profile.uploader || profile.name || profile.label || '';
  if (uploaderInput) {
    uploaderInput.value = uploaderName;
  }
  const authorName = profile.author || profile.name || profile.label || '';
  if (authorInput) {
    authorInput.value = authorName;
  }
  if (authorInputAlt) {
    authorInputAlt.value = authorName;
  }
};

const setCurrentLawyer = id => {
  if (!lawyers[id]) {
    return;
  }
  currentLawyerId = id;
  localStorage.setItem(STORAGE_KEYS.activeLawyer, id);
  applyLawyerProfile();
};

const updateCurrentLawyer = updates => {
  const profile = getCurrentLawyer();
  if (!profile) {
    return;
  }
  lawyers[currentLawyerId] = { ...profile, ...updates };
  saveLawyers(lawyers);
};

const setLoginState = isLoggedIn => {
  if (!loginView || !lawyerApp) {
    return;
  }
  loginView.classList.toggle('login-screen--active', !isLoggedIn);
  lawyerApp.classList.toggle('app-shell--active', isLoggedIn);
  lawyerApp.classList.toggle('view--active', isLoggedIn);
  document.body.classList.toggle('no-scroll', !isLoggedIn);
};

const setView = view => {
  if (loginView && lawyerView && !consoleView) {
    return;
  }
  if (consoleView && lawyerView) {
    consoleView.classList.toggle('view--active', view === 'console');
    lawyerView.classList.toggle('view--active', view === 'lawyer');
    viewTabs.forEach(tab => {
      tab.classList.toggle(
        'view-tab--active',
        tab.getAttribute('data-view') === view,
      );
    });
    return;
  }
  if (consoleView) {
    consoleView.classList.add('view--active');
  }
  if (lawyerView) {
    lawyerView.classList.add('view--active');
  }
};

const readConfig = () => ({
  apiBase: localStorage.getItem(STORAGE_KEYS.apiBase) || DEFAULTS.apiBase,
  baseModel: localStorage.getItem(STORAGE_KEYS.baseModel) || DEFAULTS.baseModel,
});

const applyConfigToInputs = () => {
  const config = readConfig();
  if (apiBaseInput) {
    apiBaseInput.value = config.apiBase;
  }
  if (apiBaseInputAlt) {
    apiBaseInputAlt.value = config.apiBase;
  }
  if (baseModelInput) {
    baseModelInput.value = config.baseModel;
  }
  if (baseModelInputAlt) {
    baseModelInputAlt.value = config.baseModel;
  }
};

const persistConfigValue = (key, value) => {
  if (!value) {
    return;
  }
  localStorage.setItem(key, value);
};

const syncInput = (source, targets) => {
  targets.forEach(target => {
    if (!target) {
      return;
    }
    if (target.value !== source.value) {
      target.value = source.value;
    }
  });
};

const linkInputs = (primary, secondary) => {
  if (!primary || !secondary) {
    return;
  }
  secondary.value = primary.value;
  primary.addEventListener('input', () => syncInput(primary, [secondary]));
  secondary.addEventListener('input', () => syncInput(secondary, [primary]));
};

const bindConfigInput = (input, key) => {
  if (!input) {
    return;
  }
  input.addEventListener('input', () => {
    persistConfigValue(key, input.value);
  });
};

const toggleModal = isOpen => {
  if (!settingsModal) {
    return;
  }
  settingsModal.classList.toggle('modal--open', isOpen);
  settingsModal.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
};

const startProgress = (progressEl, phases) => {
  if (!progressEl) {
    return [];
  }
  const label = progressEl.querySelector('.progress__label');
  const fill = progressEl.querySelector('.progress__fill');
  if (!label || !fill) {
    return [];
  }
  progressEl.classList.add('progress--active');
  label.textContent = phases[0]?.label || 'Working...';
  fill.style.width = phases[0]?.width || '10%';
  return phases.slice(1).map(phase =>
    setTimeout(() => {
      label.textContent = phase.label;
      fill.style.width = phase.width;
    }, phase.delay),
  );
};

const finishProgress = progressEl => {
  if (!progressEl) {
    return;
  }
  const label = progressEl.querySelector('.progress__label');
  const fill = progressEl.querySelector('.progress__fill');
  if (label && fill) {
    label.textContent = 'Done';
    fill.style.width = '100%';
  }
  setTimeout(() => {
    progressEl.classList.remove('progress--active');
  }, 700);
};

const showToast = (message, tone = 'info') => {
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.classList.remove('toast--info', 'toast--error');
  toast.classList.add(`toast--${tone}`);
  toast.classList.add('toast--visible');
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => {
    toast.classList.remove('toast--visible');
  }, 3200);
};

const setError = message => {
  if (!message) {
    showToast('Done.', 'info');
    return;
  }
  showToast(message, 'error');
};

const baseUrl = () => {
  const config = readConfig();
  const value = apiBaseInput?.value || apiBaseInputAlt?.value || config.apiBase;
  return value.replace(/\/+$/, '');
};

const baseModel = () => {
  const config = readConfig();
  return baseModelInput?.value || baseModelInputAlt?.value || config.baseModel;
};

const authorValue = () => authorInput?.value || authorInputAlt?.value || '';

const messageValue = () => messageInput?.value || messageInputAlt?.value || '';

const setSuggestMode = mode => {
  if (!mode) {
    return;
  }
  suggestMode = mode;
  if (suggestModeSelect) {
    suggestModeSelect.value = mode;
  }
  suggestModeButtons.forEach(button => {
    button.classList.toggle(
      'segment--active',
      button.getAttribute('data-suggest-mode') === mode,
    );
  });
};


const renderSelection = () => {
  if (selectionMeta) {
    selectionMeta.textContent = `Base: ${shortId(
      selectedBase,
    )} | Left: ${shortId(selectedLeft)} | Right: ${shortId(selectedRight)}`;
  }
};

const renderConflictPanel = commit => {
  if (!conflictTitle || !conflictList || !conflictSuggestButton) {
    return;
  }
  if (!commit) {
    conflictTitle.textContent = 'None selected';
    conflictList.innerHTML = '<p class="meta">No change selected.</p>';
    conflictSuggestButton.disabled = true;
    return;
  }
  conflictTitle.textContent = commit.message || shortId(commit.commit_id);
  const diffs = (commit.ai_meta && commit.ai_meta.clause_diffs) || [];
  const conflicts = new Set(
    (commit.ai_meta && commit.ai_meta.conflict_cids) || [],
  );
  const conflictDiffs = diffs.filter(diff => conflicts.has(diff.cid));
  if (!conflictDiffs.length) {
    conflictList.innerHTML = '<p class="meta">No conflicts in this change.</p>';
    conflictSuggestButton.disabled = true;
    return;
  }
  conflictList.innerHTML = '';
  conflictDiffs.forEach(diff => {
    const item = document.createElement('div');
    item.className = 'conflict-item';
    const heading = diff.after_heading || diff.before_heading || 'Clause';
    const beforeText = diff.before_text || '';
    const afterText = diff.after_text || '';
    item.innerHTML = `
      <strong>${diff.cid} • ${heading}</strong>
      <div class="conflict-body">
        <div>
          <span class="conflict-label">Original</span>
          <p>${beforeText || '(empty)'}</p>
        </div>
        <div>
          <span class="conflict-label">Edited</span>
          <p>${afterText || '(empty)'}</p>
        </div>
      </div>
    `;
    conflictList.appendChild(item);
  });
  conflictSuggestButton.disabled = !commit.parent || conflictDiffs.length === 0;
};

const renderCommits = () => {
  const updateSelection = (role, commitId) => {
    if (role === 'base') {
      selectedBase = commitId;
    }
    if (role === 'left') {
      selectedLeft = commitId;
    }
    if (role === 'right') {
      selectedRight = commitId;
    }
    renderSelection();
    renderCommits();
  };

  if (commitList) {
    commitList.innerHTML = '';
    if (!commits.length) {
      commitList.innerHTML = '<p class="meta">No commits yet.</p>';
    } else {
      commits.forEach(commit => {
        const card = document.createElement('div');
        card.className = 'commit-card';
        card.innerHTML = `
          <div class="commit-head">
            <span>${commit.message || 'Untitled'}</span>
            <span>${shortId(commit.commit_id)}</span>
          </div>
          <div class="commit-meta">${commit.author} | ${commit.timestamp_utc}</div>
          <div class="tag-row">
            <button class="tag ${selectedBase === commit.commit_id ? 'tag--active' : ''}" data-role="base">
              Base
            </button>
            <button class="tag ${selectedLeft === commit.commit_id ? 'tag--active' : ''}" data-role="left">
              Left
            </button>
            <button class="tag ${selectedRight === commit.commit_id ? 'tag--active' : ''}" data-role="right">
              Right
            </button>
          </div>
        `;

        card.querySelectorAll('button').forEach(button => {
          button.addEventListener('click', () => {
            updateSelection(button.getAttribute('data-role'), commit.commit_id);
          });
        });

        commitList.appendChild(card);
      });
    }
  }

  if (commitListAlt) {
    commitListAlt.innerHTML = '';
    if (!commits.length) {
      commitListAlt.innerHTML =
        '<p class="meta">No changes yet. Upload the original contract.</p>';
    } else {
      commits.forEach((commit, index) => {
        const clauseDiffs = (commit.ai_meta && commit.ai_meta.clause_diffs) || [];
        const changedCount =
          (commit.ai_meta && commit.ai_meta.changed_clause_count) || clauseDiffs.length;
        const conflictCount =
          (commit.ai_meta && commit.ai_meta.conflict_cids && commit.ai_meta.conflict_cids.length) || 0;
        const row = document.createElement('div');
        row.className = `timeline-row${selectedConflictCommit?.commit_id === commit.commit_id ? ' timeline-row--active' : ''}`;
        row.innerHTML = `
          <div class="timeline-rail">
            <div class="timeline-dot"></div>
            ${index !== commits.length - 1 ? '<div class="timeline-line"></div>' : ''}
          </div>
          <div class="timeline-card">
            <div class="commit-head">
              <span>${commit.message || 'Untitled'}</span>
              <span class="badge">${commit.author || 'Unknown'}</span>
            </div>
            <div class="commit-meta">${commit.author} | ${commit.timestamp_utc}</div>
            <div class="commit-meta muted">Change reference: ${shortId(commit.commit_id)}</div>
            <div class="commit-meta">
              Changed clauses: ${changedCount} | Conflicts: ${conflictCount}
            </div>
          </div>
        `;

        row.addEventListener('click', () => {
          selectedConflictCommit = commit;
          selectedBase = commit.parent || null;
          selectedLeft = commit.commit_id;
          selectedRight = null;
          renderSelection();
          renderConflictPanel(commit);
          renderCommits();
        });

        commitListAlt.appendChild(row);
      });
    }
  }
};

const renderMerge = () => {
  [mergeResultEl, mergeResultAlt].forEach(target => {
    if (!target) {
      return;
    }
    target.innerHTML = '';
    if (!mergeResult) {
      return;
    }
    const conflicts = mergeResult.conflicts || [];
    target.innerHTML = `
      <h3>Conflicts</h3>
      <div>${conflicts.length ? conflicts.join(', ') : 'None'}</div>
      <h3>Merge ID</h3>
      <div>${mergeResult.merge_id}</div>
    `;
  });
};

const renderSuggest = () => {
  const targets = [
    { result: suggestResultEl, actions: suggestActionsEl },
    { result: suggestResultAlt, actions: suggestActionsAlt },
  ];
  targets.forEach(target => {
    if (!target.result || !target.actions) {
      return;
    }
    target.result.innerHTML = '';
    target.actions.innerHTML = '';
    if (!suggestResult) {
      return;
    }
    const ops = suggestResult.patch_ops || [];
    const recommendations = suggestResult.clause_recommendations || [];
    const alerts = suggestResult.clause_alerts || [];
    target.result.innerHTML = `
      <h3>Suggestion ID</h3>
      <div>${suggestResult.suggestion_id}</div>
      <h3>Mode</h3>
      <div>${suggestResult.mode || 'full'}</div>
      <h3>Patch Ops</h3>
    `;
    if (ops.length) {
      ops.forEach(op => {
        const opEl = document.createElement('div');
        opEl.className = 'op';
        opEl.innerHTML = `<strong>${op.op}</strong>${op.cid}: ${op.new_text}`;
        target.result.appendChild(opEl);
      });
    } else if (recommendations.length) {
      const recHeader = document.createElement('h3');
      recHeader.textContent = 'Recommendations';
      target.result.appendChild(recHeader);
      recommendations.forEach(rec => {
        const recEl = document.createElement('div');
        recEl.className = 'op';
        recEl.innerHTML = `<strong>${rec.cid}</strong>${rec.recommendations}`;
        target.result.appendChild(recEl);
      });
    } else if (alerts.length) {
      const alertHeader = document.createElement('h3');
      alertHeader.textContent = 'Alerts';
      target.result.appendChild(alertHeader);
      alerts.forEach(alert => {
        const alertEl = document.createElement('div');
        alertEl.className = 'op';
        alertEl.innerHTML = `<strong>${alert.cid}</strong>${alert.status}: ${alert.reason || ''}`;
        target.result.appendChild(alertEl);
      });
    } else {
      const empty = document.createElement('div');
      empty.className = 'op';
      empty.textContent = 'No suggestion details returned.';
      target.result.appendChild(empty);
    }
    const skipButton = document.createElement('button');
    skipButton.className = 'btn';
    skipButton.textContent = 'Skip suggestion';
    skipButton.addEventListener('click', () => {
      suggestResult = null;
      renderSuggest();
    });
    target.actions.appendChild(skipButton);
  });
};

const renderApply = result => {
  [applyResultEl, applyResultAlt].forEach(target => {
    if (!target) {
      return;
    }
    target.innerHTML = '';
    if (!result) {
      return;
    }
    target.innerHTML = `
      <h3>New Commit</h3>
      <div>${result.new_commit_id}</div>
      <h3>Skipped Ops</h3>
      <div>${(result.skipped_ops || []).length}</div>
    `;
  });
};

const withStatus = (elements, label) => {
  [commitStatus, commitStatusAlt].forEach(status => {
    if (status) {
      status.textContent = label;
    }
  });
  elements.forEach(element => {
    if (element) {
      element.disabled = true;
    }
  });
  return () => {
    elements.forEach(element => {
      if (element) {
        element.disabled = false;
      }
    });
    [commitStatus, commitStatusAlt].forEach(status => {
      if (status) {
        status.textContent = 'Idle';
      }
    });
  };
};

const startSuggestProgress = () => {
  const progressBars = [suggestProgress, suggestProgressAlt].filter(Boolean);
  if (!progressBars.length) {
    return;
  }
  suggestPhaseTimer.forEach(timer => clearTimeout(timer));
  progressBars.forEach(progress => {
    const label = progress.querySelector('.progress__label');
    const fill = progress.querySelector('.progress__fill');
    if (!label || !fill) {
      return;
    }
    progress.classList.add('progress--active');
    label.textContent = 'Warming up model...';
    fill.style.width = '12%';
  });
  const phase1 = setTimeout(() => {
    progressBars.forEach(progress => {
      const label = progress.querySelector('.progress__label');
      const fill = progress.querySelector('.progress__fill');
      if (label && fill) {
        label.textContent = 'Analyzing conflicts...';
        fill.style.width = '48%';
      }
    });
  }, 1200);
  const phase2 = setTimeout(() => {
    progressBars.forEach(progress => {
      const label = progress.querySelector('.progress__label');
      const fill = progress.querySelector('.progress__fill');
      if (label && fill) {
        label.textContent = 'Generating suggestion...';
        fill.style.width = '78%';
      }
    });
  }, 2600);
  suggestPhaseTimer = [phase1, phase2];
};

const finishSuggestProgress = () => {
  const progressBars = [suggestProgress, suggestProgressAlt].filter(Boolean);
  if (!progressBars.length) {
    return;
  }
  suggestPhaseTimer.forEach(timer => clearTimeout(timer));
  progressBars.forEach(progress => {
    const label = progress.querySelector('.progress__label');
    const fill = progress.querySelector('.progress__fill');
    if (label && fill) {
      label.textContent = 'Done';
      fill.style.width = '100%';
    }
    setTimeout(() => {
      progress.classList.remove('progress--active');
    }, 700);
  });
};

const loadCommits = async () => {
  setError(null);
  const done = withStatus([refreshCommitsButton], 'Loading commits');
  try {
    const res = await fetch(`${baseUrl()}/commits`);
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload?.detail || 'Failed to load commits.');
    }
    commits = payload.commits || [];
    if (!consoleView) {
      selectedConflictCommit = commits[0] || null;
      if (selectedConflictCommit) {
        selectedLeft = selectedConflictCommit.commit_id;
        selectedBase = selectedConflictCommit.parent || null;
        selectedRight = null;
        renderConflictPanel(selectedConflictCommit);
      } else {
        renderConflictPanel(null);
      }
      renderSelection();
    }
    renderCommits();
  } catch (err) {
    setError(err.message || 'Failed to load commits.');
  } finally {
    done();
  }
};

const runUpload = async () => {
  if (!uploadFileInput || !uploadFileInput.files || !uploadFileInput.files.length) {
    setError('Select a DOCX or TXT file to upload.');
    return;
  }
  setError(null);
  const done = withStatus([refreshCommitsButtonAlt], 'Uploading');
  const uploadTimers = startProgress(uploadProgress, [
    { label: 'Uploading file...', width: '18%', delay: 0 },
    { label: 'Parsing clauses...', width: '52%', delay: 1200 },
    { label: 'Comparing against head...', width: '78%', delay: 2600 },
  ]);
  try {
    const formData = new FormData();
    const author = uploaderInput ? uploaderInput.value : 'Unknown';
    const matterName = matterNameInput ? matterNameInput.value : '';
    const modelPath = baseModel();
    formData.append('author', author);
    formData.append('message', matterName ? `Upload: ${matterName}` : `${author} upload`);
    formData.append('parse_mode', 'ai');
    if (modelPath) {
      formData.append('base_model', modelPath);
    }
    formData.append('file', uploadFileInput.files[0]);
    const res = await fetch(`${baseUrl()}/upload`, {
      method: 'POST',
      body: formData,
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload?.detail || 'Upload failed.');
    }
    await loadCommits();
    showToast('Upload complete.', 'info');
  } catch (err) {
    setError(err.message || 'Upload failed.');
  } finally {
    uploadTimers.forEach(timer => clearTimeout(timer));
    finishProgress(uploadProgress);
    done();
  }
};

const resetCommits = async () => {
  if (!confirm('Delete all commits in this repo? This cannot be undone.')) {
    return;
  }
  setError(null);
  const done = withStatus([resetCommitsButton], 'Clearing commits');
  try {
    const res = await fetch(`${baseUrl()}/commits`, { method: 'DELETE' });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload?.detail || 'Failed to clear commits.');
    }
    commits = [];
    selectedBase = null;
    selectedLeft = null;
    selectedRight = null;
    mergeResult = null;
    suggestResult = null;
    renderSelection();
    renderCommits();
    renderMerge();
    renderSuggest();
    renderApply(null);
    showToast('Commits cleared.', 'info');
  } catch (err) {
    setError(err.message || 'Failed to clear commits.');
  } finally {
    done();
  }
};

const runMerge = async () => {
  if (!selectedBase || !selectedLeft) {
    setError(
      consoleView
        ? 'Select base and left commits before merging.'
        : 'Need at least two commits to compare changes.',
    );
    return;
  }
  setError(null);
  mergeResult = null;
  renderMerge();
  const done = withStatus(
    [runMergeButton, runMergeButtonAlt],
    'Merging',
  );
  try {
    const res = await fetch(`${baseUrl()}/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_id: selectedBase,
        left_id: selectedLeft,
        right_id: selectedRight || undefined,
      }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload?.detail || 'Merge failed.');
    }
    mergeResult = payload;
    renderMerge();
  } catch (err) {
    setError(err.message || 'Merge failed.');
  } finally {
    done();
  }
};

const runSuggest = async () => {
  if (!mergeResult?.merge_id) {
    setError('Run merge before requesting suggestions.');
    return;
  }
  setError(null);
  suggestResult = null;
  renderSuggest();
  startSuggestProgress();
  const done = withStatus(
    [runSuggestButton, runSuggestButtonAlt],
    'Generating',
  );
  try {
    const res = await fetch(`${baseUrl()}/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        merge_id: mergeResult.merge_id,
        base_model: baseModel() || undefined,
        mode: suggestMode || 'full',
        no_adapter: true,
      }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload?.detail || 'Suggest failed.');
    }
    suggestResult = payload.suggestion;
    renderSuggest();
  } catch (err) {
    setError(err.message || 'Suggest failed.');
  } finally {
    done();
    finishSuggestProgress();
  }
};

const runApply = async () => {
  if (!suggestResult?.suggestion_id) {
    setError('Request a suggestion before applying.');
    return;
  }
  setError(null);
  renderApply(null);
  const done = withStatus([runApplyButton, runApplyButtonAlt], 'Applying');
  try {
    const res = await fetch(`${baseUrl()}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        suggestion_id: suggestResult.suggestion_id,
        author: authorValue(),
        msg: messageValue(),
      }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload?.detail || 'Apply failed.');
    }
    renderApply(payload);
    await loadCommits();
  } catch (err) {
    setError(err.message || 'Apply failed.');
  } finally {
    done();
  }
};

if (refreshCommitsButton) {
  refreshCommitsButton.addEventListener('click', loadCommits);
}
if (resetCommitsButton) {
  resetCommitsButton.addEventListener('click', resetCommits);
}
if (refreshCommitsButtonAlt) {
  refreshCommitsButtonAlt.addEventListener('click', runUpload);
}
if (runMergeButton) {
  runMergeButton.addEventListener('click', runMerge);
}
if (runMergeButtonAlt) {
  runMergeButtonAlt.addEventListener('click', runMerge);
}
if (runSuggestButton) {
  runSuggestButton.addEventListener('click', runSuggest);
}
if (runSuggestButtonAlt) {
  runSuggestButtonAlt.addEventListener('click', runSuggest);
}
if (runApplyButton) {
  runApplyButton.addEventListener('click', runApply);
}
if (runApplyButtonAlt) {
  runApplyButtonAlt.addEventListener('click', runApply);
}
if (conflictSuggestButton) {
  conflictSuggestButton.addEventListener('click', async () => {
    await runMerge();
    if (mergeResult && mergeResult.merge_id) {
      await runSuggest();
    }
  });
}

if (suggestModeSelect) {
  suggestModeSelect.addEventListener('change', event => {
    const target = event.target;
    setSuggestMode(target && target.value ? target.value : null);
  });
}
suggestModeButtons.forEach(button => {
  button.addEventListener('click', () => {
    setSuggestMode(button.getAttribute('data-suggest-mode'));
  });
});
viewTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    setView(tab.getAttribute('data-view'));
  });
});

loginButtons.forEach(button => {
  button.addEventListener('click', () => {
    setCurrentLawyer(button.getAttribute('data-login-lawyer'));
    setLoginState(true);
  });
});
if (logoutButton) {
  logoutButton.addEventListener('click', () => {
    setLoginState(false);
  });
}
if (uploaderInput) {
  uploaderInput.addEventListener('input', () => {
    updateCurrentLawyer({ uploader: uploaderInput.value });
  });
}
if (authorInput) {
  authorInput.addEventListener('input', () => {
    updateCurrentLawyer({ author: authorInput.value });
  });
}
if (authorInputAlt) {
  authorInputAlt.addEventListener('input', () => {
    updateCurrentLawyer({ author: authorInputAlt.value });
  });
}

applyConfigToInputs();
linkInputs(apiBaseInput, apiBaseInputAlt);
linkInputs(baseModelInput, baseModelInputAlt);
bindConfigInput(apiBaseInput, STORAGE_KEYS.apiBase);
bindConfigInput(apiBaseInputAlt, STORAGE_KEYS.apiBase);
bindConfigInput(baseModelInput, STORAGE_KEYS.baseModel);
bindConfigInput(baseModelInputAlt, STORAGE_KEYS.baseModel);
linkInputs(authorInput, authorInputAlt);
linkInputs(messageInput, messageInputAlt);
applyLawyerProfile();
setLoginState(false);

setSuggestMode(suggestMode);
setView(consoleView && lawyerView ? 'console' : lawyerView ? 'lawyer' : 'console');
renderSelection();
loadCommits();

window.addEventListener('storage', event => {
  if (!event.key) {
    return;
  }
  if (
    event.key === STORAGE_KEYS.apiBase ||
    event.key === STORAGE_KEYS.baseModel
  ) {
    applyConfigToInputs();
  }
});

if (openSettingsButton) {
  openSettingsButton.addEventListener('click', () => {
    toggleModal(true);
  });
}

if (settingsModal) {
  settingsModal.addEventListener('click', event => {
    const target = event.target;
    if (target && target.hasAttribute('data-modal-close')) {
      toggleModal(false);
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      toggleModal(false);
    }
  });
}
