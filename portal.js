// Answer checks and hints. A submitted answer is used as the key to decrypt that
// envelope's confirmation (see build.mjs); a wrong answer simply fails to decrypt.
(function () {
  const DATA = window.CASE_DATA;
  const STORAGE_KEY = 'case-25-10-4471';
  const HINT_LABELS = ['Hint 1', 'Hint 2', 'Hint 3 (gives the answer)'];

  const bytes = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const text = (b64) => new TextDecoder().decode(bytes(b64));

  function load() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch (e) { return {}; }
  }
  function save(state) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { /* storage unavailable */ }
  }

  // state = { answers: { [caseId]: string }, hints: { [caseId]: number } }
  const state = Object.assign({ answers: {}, hints: {} }, load());

  // Wrong answers lock the envelope's form for a while, longer each time.
  // Kept under its own key so "Erase my progress" does not clear a running cooldown.
  const COOLDOWN_KEY = STORAGE_KEY + '-cooldown';
  const COOLDOWN_SECONDS = [30, 60, 120, 300];
  // cooldowns = { [caseId]: { wrong: number, until: epoch ms } }
  let cooldowns = {};
  try { cooldowns = JSON.parse(localStorage.getItem(COOLDOWN_KEY)) || {}; } catch (e) { /* storage unavailable */ }
  function saveCooldowns() {
    try { localStorage.setItem(COOLDOWN_KEY, JSON.stringify(cooldowns)); } catch (e) { /* storage unavailable */ }
  }

  async function decrypt(data, answer) {
    const material = await crypto.subtle.importKey(
      'raw', new TextEncoder().encode(answer), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: bytes(data.salt), iterations: data.iter, hash: 'SHA-256' },
      material, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
    for (const p of data.payloads) {
      try {
        const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes(p.iv) }, key, bytes(p.ct));
        return new TextDecoder().decode(plain);
      } catch (e) { /* not this payload */ }
    }
    return null;
  }

  function readAnswer(section, id) {
    if (id === 1) return section.querySelector('#a1').value;
    if (id === 2) {
      return [...section.querySelectorAll('input[name="a2"]:checked')].map((i) => i.value).sort().join('+');
    }
    if (id === 3) {
      const picked = section.querySelector('input[name="a3"]:checked');
      return picked ? picked.value : '';
    }
    return section.querySelector('#a4who').value + '|' + section.querySelector('#a4why').value;
  }

  const sections = DATA.map((data) => {
    const section = document.querySelector(`.case[data-case="${data.id}"]`);
    const form = section.querySelector('form');

    const feedback = document.createElement('p');
    feedback.className = 'feedback';
    feedback.setAttribute('role', 'alert');
    form.after(feedback);

    const result = document.createElement('div');
    result.className = 'result';
    result.hidden = true;
    feedback.after(result);

    const lockedNote = document.createElement('p');
    lockedNote.className = 'locked-note';
    lockedNote.textContent = `Confirm Envelope ${data.id - 1} first.`;
    lockedNote.hidden = true;
    section.append(lockedNote);

    const hints = document.createElement('div');
    hints.className = 'hints';
    const buttons = document.createElement('div');
    buttons.className = 'hint-buttons';
    const shown = document.createElement('div');
    hints.append(buttons, shown);
    section.append(hints);

    const hintButtons = data.hints.map((_, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = HINT_LABELS[i];
      b.addEventListener('click', () => {
        state.hints[data.id] = Math.max(state.hints[data.id] || 0, i + 1);
        save(state);
        renderHints();
      });
      buttons.append(b);
      return b;
    });

    function renderHints() {
      const revealed = state.hints[data.id] || 0;
      shown.replaceChildren();
      data.hints.slice(0, revealed).forEach((h, i) => {
        const div = document.createElement('div');
        div.className = 'hint';
        const label = document.createElement('b');
        label.textContent = `Hint ${i + 1}`;
        div.append(label, text(h));
        shown.append(div);
      });
      hintButtons.forEach((b, i) => { b.disabled = i !== revealed; b.hidden = i < revealed; });
    }

    function showSolved(html) {
      result.innerHTML = html;
      result.hidden = false;
      feedback.textContent = '';
      section.classList.add('solved');
    }

    const submit = form.querySelector('button[type="submit"]');
    let timer = null;

    // Disables the submit button and counts down until the cooldown ends.
    function runCooldown(message) {
      clearInterval(timer);
      const tick = () => {
        const left = Math.ceil(((cooldowns[data.id] || {}).until - Date.now()) / 1000);
        if (!(left > 0)) {
          clearInterval(timer);
          submit.disabled = false;
          feedback.textContent = message;
          return;
        }
        submit.disabled = true;
        const clock = Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0');
        feedback.textContent = `${message} Next attempt in ${clock}.`.trim();
      };
      tick();
      if (submit.disabled) timer = setInterval(tick, 1000);
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (submit.disabled) return;
      feedback.textContent = '';
      const answer = readAnswer(section, data.id);
      if (data.id === 2 && answer.split('+').length !== 2) {
        feedback.textContent = 'Select exactly two players.';
        return;
      }
      if (!window.crypto || !crypto.subtle) {
        feedback.textContent = 'This page must be opened over https.';
        return;
      }
      submit.disabled = true;
      const html = await decrypt(data, answer);
      submit.disabled = false;
      if (html) {
        state.answers[data.id] = answer;
        save(state);
        delete cooldowns[data.id];
        saveCooldowns();
        showSolved(html);
        updateLocks();
      } else {
        const wrong = ((cooldowns[data.id] || {}).wrong || 0) + 1;
        const seconds = COOLDOWN_SECONDS[Math.min(wrong, COOLDOWN_SECONDS.length) - 1];
        cooldowns[data.id] = { wrong, until: Date.now() + seconds * 1000 };
        saveCooldowns();
        runCooldown('Not confirmed. That conclusion does not fit the evidence.');
      }
    });

    renderHints();
    runCooldown('');
    return { data, section, lockedNote, showSolved };
  });

  function updateLocks() {
    sections.forEach((s, i) => {
      const locked = i > 0 && !sections[i - 1].section.classList.contains('solved');
      s.section.classList.toggle('locked', locked);
      s.lockedNote.hidden = !locked;
    });
  }

  document.getElementById('reset').addEventListener('click', () => {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* storage unavailable */ }
    location.reload();
  });

  // Restore confirmed envelopes from this device, in order.
  (async function restore() {
    updateLocks();
    if (!window.crypto || !crypto.subtle) return;
    for (const s of sections) {
      const answer = state.answers[s.data.id];
      if (!answer) break;
      const html = await decrypt(s.data, answer);
      if (!html) break;
      s.showSolved(html);
      updateLocks();
    }
  })();
})();
