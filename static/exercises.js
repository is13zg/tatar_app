/* Раннер урока и упражнения TT-Learn Kids.
   Использование (lesson.html): Lesson.run(container, {daily:true} | {themeId, lessonNo}) */
(function () {
  'use strict';

  // ---------- общие утилиты ----------
  function token() { return localStorage.getItem('token'); }
  function authHeaders() { const t = token(); return t ? { 'Authorization': 'Bearer ' + t } : {}; }

  async function api(path, opts = {}) {
    const res = await fetch(path, { ...opts, headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(opts.headers || {}) } });
    if (res.status === 401) { location.href = '/static/pages/login.html'; throw new Error('401'); }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  const audioEl = new Audio();
  function playAudio(url) {
    return new Promise(resolve => {
      if (!url) return resolve();
      // татарское слово главнее: глушим инструкцию, чтобы голоса не накладывались
      try { speechSynthesis.cancel(); } catch (e) {}
      try { ruAudioEl.pause(); } catch (e) {}
      try { audioEl.pause(); audioEl.currentTime = 0; } catch (e) {}
      audioEl.src = url;
      audioEl.onended = () => resolve();
      audioEl.onerror = () => resolve();
      audioEl.play().catch(() => resolve());
      setTimeout(resolve, 10000); // страховка
    });
  }

  // Записанные инструкции (Сбер SaluteSpeech, tools/gen_ru_instructions.py).
  // Если файла нет — фолбэк на браузерный синтез (он для русского звучит приемлемо).
  const INSTR_AUDIO = {
    'Новое слово!': 'novoe_slovo',
    'Послушай и найди картинку': 'najdi_kartinku',
    'Это правильная картинка?': 'pravilnaya_kartinka',
    'Найди пары': 'najdi_pary',
    'Разложи по корзинкам': 'razlozhi_po_korzinkam',
    'Выбери кнопку со словом с картинки': 'vyberi_knopku',
    'Собери слово из букв': 'soberi_slovo',
    'Повтори за диктором': 'povtori_za_diktorom',
    'Молодец!': 'molodec',
    'Молодец! Отлично!': 'molodec_otlichno',
  };
  const missingInstr = new Set();
  const ruAudioEl = new Audio();
  let speakToken = 0; // каждый новый голос отменяет предыдущий — никаких наложений

  function speakRuBrowser(text) {
    // Браузерный синтез: ждём, пока договорит, — иначе следующее аудио ляжет поверх.
    return new Promise(resolve => {
      try {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'ru-RU'; u.rate = 0.95;
        u.onend = () => resolve();
        u.onerror = () => resolve();
        speechSynthesis.cancel();
        speechSynthesis.speak(u);
        setTimeout(resolve, 5000); // страховка
      } catch (e) { resolve(); }
    });
  }

  function speakRu(text) {
    // Файл доиграл → resolve. Прерывание НОВЫМ звуком — это не ошибка файла:
    // раньше такой catch помечал файл «отсутствующим» и запускал браузерный
    // синтез ПАРАЛЛЕЛЬНО следующему файлу — отсюда каша из голосов.
    return new Promise(resolve => {
      const my = ++speakToken;
      const key = INSTR_AUDIO[text];
      if (!key || missingInstr.has(key)) { speakRuBrowser(text).then(resolve); return; }
      try { speechSynthesis.cancel(); } catch (e) {}
      try { ruAudioEl.pause(); ruAudioEl.currentTime = 0; } catch (e) {}
      ruAudioEl.src = `/static/voice/ru/${key}.wav`;
      ruAudioEl.onended = () => resolve();
      ruAudioEl.onerror = () => {
        missingInstr.add(key); // реальная ошибка загрузки (404/сеть)
        if (my === speakToken) { speakRuBrowser(text).then(resolve); } else { resolve(); }
      };
      ruAudioEl.play().catch(() => resolve()); // перебили другим звуком — тихо выходим
      setTimeout(resolve, 4000); // страховка
    });
  }

  async function speakThenPlay(instrText, wordAudioUrl) {
    await speakRu(instrText);
    await sleep(150);
    await playAudio(wordAudioUrl);
  }

  const sfxGood = new Audio('/static/sounds/success.mp3');
  const sfxBad = new Audio('/static/sounds/error.mp3');
  sfxGood.volume = 0.45; sfxBad.volume = 0.45;
  function playFx(ok) {
    const el = ok ? sfxGood : sfxBad;
    try { el.pause(); el.currentTime = 0; } catch (e) {}
    return new Promise(r => { el.onended = () => r(); el.play().catch(() => r()); setTimeout(r, 1500); });
  }

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; // textContent: данные из БД не должны исполняться как HTML
    return n;
  }

  function visual(obj, big) {
    // картинка слова или крупный эмодзи
    const hasImg = obj.image_url && !obj.image_url.includes('noimg');
    if (hasImg) {
      const img = document.createElement('img');
      img.src = obj.image_url; img.alt = '';
      return img;
    }
    return el('div', 'emoji', obj.emoji || '❓');
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  function shuffled(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function confetti() {
    const box = el('div', 'confetti');
    const colors = ['#f97316', '#8b5cf6', '#22c55e', '#eab308', '#3b82f6', '#ec4899'];
    for (let i = 0; i < 80; i++) {
      const p = document.createElement('i');
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[i % colors.length];
      p.style.animationDuration = (2.2 + Math.random() * 2) + 's';
      p.style.animationDelay = (Math.random() * 0.8) + 's';
      p.style.borderRadius = Math.random() > 0.5 ? '50%' : '3px';
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(() => box.remove(), 5200);
  }

  let banner;
  function feedback(ok, text) {
    if (!banner) { banner = el('div', 'feedback-banner'); document.body.appendChild(banner); }
    banner.className = 'feedback-banner ' + (ok ? 'good' : 'bad');
    banner.textContent = text || (ok ? 'Дөрес! 🎉' : 'Хата 😅');
    requestAnimationFrame(() => banner.classList.add('show'));
    setTimeout(() => banner.classList.remove('show'), 1300);
  }

  // --- надёжная доставка ответов: при обрыве сети копим в localStorage и досылаем ---
  function queuePush(name, payload) {
    try {
      const q = JSON.parse(localStorage.getItem(name) || '[]');
      q.push(payload);
      localStorage.setItem(name, JSON.stringify(q.slice(-200)));
    } catch (e) {}
  }

  async function flushQueues() {
    try {
      const answers = JSON.parse(localStorage.getItem('pending_answers') || '[]');
      if (answers.length) {
        localStorage.removeItem('pending_answers');
        for (const a of answers) {
          await api('/lesson/answer', { method: 'POST', body: JSON.stringify(a) }).catch(() => queuePush('pending_answers', a));
        }
      }
      const completes = JSON.parse(localStorage.getItem('pending_completes') || '[]');
      if (completes.length) {
        localStorage.removeItem('pending_completes');
        for (const c of completes) {
          await api('/lesson/complete', { method: 'POST', body: JSON.stringify(c) }).catch(() => queuePush('pending_completes', c));
        }
      }
    } catch (e) {}
  }
  flushQueues();

  function reportAnswer(wordId, ok, type) {
    const payload = { word_id: wordId, is_correct: ok, exercise_type: type };
    api('/lesson/answer', { method: 'POST', body: JSON.stringify(payload) })
      .catch(() => queuePush('pending_answers', payload));
  }

  async function reportComplete(payload) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        return await api('/lesson/complete', { method: 'POST', body: JSON.stringify(payload) });
      } catch (e) {
        await sleep(800 * (attempt + 1));
      }
    }
    queuePush('pending_completes', payload); // дошлём при следующем заходе
    return null;
  }

  // ---------- упражнения ----------
  // каждый рендерер: (item, screen, done) => void; done({scored, ok})

  function rCard(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🆕 Новое слово'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(w)); screen.appendChild(vis);
    screen.appendChild(el('div', 'word-big', w.text_tt));
    screen.appendChild(el('div', 'word-small', w.text_ru));
    const row = el('div', ''); row.style.cssText = 'display:flex;gap:12px;align-items:center;margin-top:14px;';
    const play = el('button', 'play-btn', '🔊');
    play.onclick = () => playAudio(w.audio_url);
    const next = el('button', 'kid-btn', 'Дальше ➜');
    next.onclick = () => done({ scored: false });
    row.appendChild(play); row.appendChild(next); screen.appendChild(row);
    speakThenPlay('Новое слово!', w.audio_url);
  }

  function rPickImage(item, screen, done) {
    screen.appendChild(el('div', 'instr', '👂 Послушай и найди картинку'));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:14px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    head.appendChild(el('div', 'word-big', item.text_tt));
    screen.appendChild(head);
    const grid = el('div', 'tile-grid'); screen.appendChild(grid);
    let locked = false;
    shuffled(item.options).forEach(opt => {
      const t = el('button', 'tile');
      t.appendChild(visual(opt));
      t.onclick = async () => {
        if (locked) return; locked = true;
        const ok = opt.id === item.word_id;
        reportAnswer(item.word_id, ok, 'pick_image');
        t.classList.add(ok ? 'good' : 'bad');
        if (!ok) {
          [...grid.children].forEach(c => { if (c._id === item.word_id) c.classList.add('good'); else if (c !== t) c.classList.add('dim'); });
        }
        feedback(ok); await playFx(ok); await sleep(700);
        done({ scored: true, ok });
      };
      t._id = opt.id;
      grid.appendChild(t);
    });
    speakThenPlay('Послушай и найди картинку', item.audio_url);
  }

  function rYesNo(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🤔 Это правильная картинка?'));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    head.appendChild(el('div', 'word-big', item.text_tt));
    screen.appendChild(head);
    const vis = el('div', 'big-visual'); vis.appendChild(visual(item.shown)); screen.appendChild(vis);
    const row = el('div', 'yn-row');
    let locked = false;
    const answer = async (saidYes) => {
      if (locked) return; locked = true;
      const ok = saidYes === item.is_match;
      reportAnswer(item.word_id, ok, 'yes_no');
      feedback(ok); await playFx(ok); await sleep(500);
      done({ scored: true, ok });
    };
    const yes = el('button', 'kid-btn yn-yes', '👍');
    const no = el('button', 'kid-btn yn-no', '👎');
    yes.onclick = () => answer(true);
    no.onclick = () => answer(false);
    row.appendChild(yes); row.appendChild(no); screen.appendChild(row);
    speakThenPlay('Это правильная картинка?', item.audio_url);
  }

  function rMemory(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🃏 Найди пары: картинка и звук'));
    const grid = el('div', 'mem-grid'); screen.appendChild(grid);
    const cards = [];
    item.pairs.forEach(p => {
      cards.push({ pair: p, kind: 'img' });
      cards.push({ pair: p, kind: 'audio' });
    });
    let open = null, matched = 0, wrong = 0, locked = false;
    shuffled(cards).forEach(c => {
      const b = el('button', 'mem-card', '❓');
      b.onclick = async () => {
        if (locked || b.classList.contains('open') || b.classList.contains('matched')) return;
        b.classList.add('open'); b.innerHTML = '';
        if (c.kind === 'img') b.appendChild(visual(c.pair));
        else { b.textContent = '🔊'; playAudio(c.pair.audio_url); }
        if (!open) { open = { b, c }; return; }
        locked = true;
        const isMatch = open.c.pair.word_id === c.pair.word_id && open.c.kind !== c.kind;
        if (isMatch) {
          await sleep(500);
          b.classList.add('matched'); open.b.classList.add('matched');
          matched++;
          reportAnswer(c.pair.word_id, true, 'memory');
          playFx(true);
        } else {
          wrong++;
          await sleep(900);
          [b, open.b].forEach(x => { x.classList.remove('open'); x.textContent = '❓'; });
        }
        open = null; locked = false;
        if (matched === item.pairs.length) {
          const ok = wrong <= 2;
          feedback(ok, ok ? 'Дөрес! 🎉' : 'Молодец, но потренируйся ещё!');
          await sleep(900);
          done({ scored: true, ok });
        }
      };
      grid.appendChild(b);
    });
    speakRu('Найди пары');
  }

  function rSortBaskets(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🧺 Разложи по корзинкам: нажми картинку, потом корзинку'));
    const basketsRow = el('div', 'baskets'); screen.appendChild(basketsRow);
    const itemsRow = el('div', 'sort-items'); screen.appendChild(itemsRow);
    let selected = null, wrong = 0, placed = 0, lockedAll = false;
    const baskets = {};
    item.baskets.forEach(b => {
      const bx = el('div', 'basket');
      bx.appendChild(el('span', 'icon', b.icon_emoji));
      bx.appendChild(el('div', '', b.title_ru));
      bx.appendChild(el('div', 'caught', ''));
      bx.onclick = async () => {
        if (!selected || lockedAll) return;
        const it = selected; selected = null;
        it.node.classList.remove('selected');
        const ok = it.data.basket === b.id;
        if (ok) {
          placed++;
          bx.querySelector('.caught').textContent += it.data.emoji || '🖼️';
          it.node.remove();
          reportAnswer(it.data.word_id, true, 'sort_baskets');
          playAudio(it.data.audio_url);
        } else {
          wrong++;
          reportAnswer(it.data.word_id, false, 'sort_baskets');
          it.node.querySelector('.tile').classList.add('bad');
          playFx(false);
          setTimeout(() => it.node.querySelector('.tile').classList.remove('bad'), 500);
        }
        Object.values(baskets).forEach(x => x.classList.remove('target'));
        if (placed === item.items.length) {
          lockedAll = true;
          const allOk = wrong === 0;
          feedback(allOk, allOk ? 'Дөрес! 🎉' : 'Готово!');
          await playFx(allOk); await sleep(600);
          done({ scored: true, ok: allOk });
        }
      };
      baskets[b.id] = bx;
      basketsRow.appendChild(bx);
    });
    item.items.forEach(d => {
      const wrap = el('div', 'sort-item');
      const t = el('button', 'tile');
      t.appendChild(visual(d));
      t.onclick = () => {
        if (lockedAll) return;
        if (selected) selected.node.classList.remove('selected');
        selected = { node: wrap, data: d };
        wrap.classList.add('selected');
        playAudio(d.audio_url);
        Object.values(baskets).forEach(x => x.classList.add('target'));
      };
      wrap.appendChild(t);
      itemsRow.appendChild(wrap);
    });
    speakRu('Разложи по корзинкам');
  }

  function rPickWordAudio(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🔊 Как звучит это слово? Слушай и выбери'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(item.shown)); screen.appendChild(vis);
    screen.appendChild(el('div', 'word-small', item.shown.text_ru || ''));
    const row = el('div', ''); row.style.cssText = 'display:flex;gap:16px;justify-content:center;margin-top:14px;';
    const colors = ['#8b5cf6', '#f97316', '#0ea5e9'];
    let locked = false, played = false, selected = null;
    const confirmBtn = el('button', 'kid-btn', '✔ Это оно!');
    confirmBtn.style.cssText = 'margin-top:14px;display:none;';
    // клиентское перемешивание: порядок кнопок и порядок прослушивания
    // независимы и от сервера, и друг от друга — позиция звука ничего не выдаёт
    const buttons = shuffled(item.options).map((o, i) => {
      const b = el('button', 'play-btn', '🔊');
      b.style.background = colors[i % colors.length];
      b.style.opacity = '0.5'; // пока идёт прослушивание — «спит»
      b.onclick = async () => {
        if (locked || !played) return;
        // тап = прослушать и выбрать; подтверждение — отдельной кнопкой
        selected = { b, o };
        buttons.forEach(x => { x.b.style.outline = 'none'; x.b.style.transform = ''; });
        b.style.outline = '6px solid #fbbf24';
        b.style.transform = 'scale(1.1)';
        confirmBtn.style.display = 'inline-flex';
        playAudio(o.audio_url);
      };
      row.appendChild(b);
      return { b, o };
    });
    screen.appendChild(row);
    screen.appendChild(confirmBtn);

    confirmBtn.onclick = async () => {
      if (locked || !selected) return; locked = true;
      const ok = selected.o.id === item.word_id;
      reportAnswer(item.word_id, ok, 'pick_word_audio');
      if (!ok) {
        // показать правильную кнопку и дать её услышать
        const right = buttons.find(x => x.o.id === item.word_id);
        if (right) { right.b.style.outline = '6px solid #22c55e'; }
        feedback(false); await playFx(false);
        if (right) await playAudio(right.o.audio_url);
        await sleep(400);
      } else {
        feedback(true); await playFx(true); await sleep(400);
      }
      done({ scored: true, ok });
    };

    // автопроигрывание вариантов по очереди с подсветкой, затем можно выбирать
    (async () => {
      await sleep(400);
      for (const { b, o } of shuffled(buttons)) {
        b.style.transform = 'scale(1.18)';
        await playAudio(o.audio_url);
        b.style.transform = '';
        await sleep(250);
      }
      played = true;
      buttons.forEach(x => { x.b.style.opacity = '1'; });
      speakRu('Выбери кнопку со словом с картинки');
    })();
  }

  function rBuildWord(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🧩 Собери слово из букв'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(item)); screen.appendChild(vis);
    const play = el('button', 'play-btn small', '🔊');
    play.style.margin = '0 auto'; play.style.display = 'block';
    play.onclick = () => playAudio(item.audio_url);
    screen.appendChild(play);
    const slots = el('div', 'slots'); screen.appendChild(slots);
    const letters = el('div', 'letters'); screen.appendChild(letters);
    const word = item.text_tt;
    let pos = 0, wrong = 0;
    const slotEls = [...word].map(() => { const s = el('div', 'slot', ''); slots.appendChild(s); return s; });
    [...item.letters].forEach(ch => {
      const b = el('button', 'letter-tile', ch);
      b.onclick = async () => {
        if (ch === word[pos]) {
          slotEls[pos].textContent = ch; slotEls[pos].classList.add('filled');
          b.disabled = true; pos++;
          if (pos === word.length) {
            const ok = wrong <= 1;
            reportAnswer(item.word_id, ok, 'build_word');
            await playAudio(item.audio_url);
            feedback(ok); await playFx(ok); await sleep(500);
            done({ scored: true, ok });
          }
        } else {
          wrong++;
          b.classList.add('bad'); playFx(false);
          setTimeout(() => b.classList.remove('bad'), 450);
        }
      };
      letters.appendChild(b);
    });
    speakThenPlay('Собери слово из букв', item.audio_url);
  }

  function rRepeatAfter(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🎤 Повтори за диктором!'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(w)); screen.appendChild(vis);
    screen.appendChild(el('div', 'word-big', w.text_tt));
    const row = el('div', ''); row.style.cssText = 'display:flex;gap:16px;align-items:center;justify-content:center;margin-top:14px;';
    const play = el('button', 'play-btn', '🔊');
    play.onclick = () => playAudio(w.audio_url);
    row.appendChild(play);

    const mic = el('button', 'mic-btn', '🎤');
    row.appendChild(mic);
    screen.appendChild(row);
    const hint = el('div', 'word-small', 'Нажми 🎤 и повтори слово');
    hint.style.marginTop = '10px';
    screen.appendChild(hint);

    let recorder = null, chunks = [], myUrl = null;
    mic.onclick = async () => {
      if (recorder && recorder.state === 'recording') { recorder.stop(); return; }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recorder = new MediaRecorder(stream);
        chunks = [];
        recorder.ondataavailable = e => chunks.push(e.data);
        recorder.onstop = () => {
          stream.getTracks().forEach(t => t.stop());
          mic.classList.remove('rec'); mic.textContent = '🎤';
          myUrl = URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
          hint.textContent = 'Послушай себя и диктора — похоже?';
          showCompare();
        };
        recorder.start();
        mic.classList.add('rec'); mic.textContent = '⏹';
        hint.textContent = 'Говори! Потом нажми ⏹';
        setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 5000);
      } catch (e) {
        hint.textContent = 'Микрофон недоступен — просто повтори вслух!';
        showNext();
      }
    };

    let compareShown = false;
    function showCompare() {
      if (compareShown) return; compareShown = true;
      const cmp = el('div', '');
      cmp.style.cssText = 'display:flex;gap:12px;justify-content:center;margin-top:14px;';
      const me = el('button', 'kid-btn ghost', '▶️ Я');
      me.onclick = () => { const a = new Audio(myUrl); a.play(); };
      const dictor = el('button', 'kid-btn ghost', '▶️ Диктор');
      dictor.onclick = () => playAudio(w.audio_url);
      cmp.appendChild(me); cmp.appendChild(dictor);
      screen.appendChild(cmp);
      showNext();
    }
    function showNext() {
      const next = el('button', 'kid-btn', 'Получилось! ➜');
      next.style.marginTop = '14px';
      next.onclick = () => { reportAnswer(w.id, true, 'repeat_after'); done({ scored: false }); };
      screen.appendChild(next);
    }
    speakThenPlay('Повтори за диктором', w.audio_url);
  }

  const RENDERERS = {
    card: rCard,
    pick_image: rPickImage,
    yes_no: rYesNo,
    memory: rMemory,
    sort_baskets: rSortBaskets,
    pick_word_audio: rPickWordAudio,
    build_word: rBuildWord,
    repeat_after: rRepeatAfter,
  };

  // ---------- раннер ----------
  async function run(container, opts) {
    container.innerHTML = '';
    const top = el('div', 'kid-top');
    const back = el('button', 'kid-back', '←');
    back.onclick = () => {
      // подтверждение выхода — случайный тап не должен терять урок
      if (document.getElementById('exit-confirm')) return;
      const overlay = el('div', '');
      overlay.id = 'exit-confirm';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:grid;place-items:center;z-index:70;padding:20px;';
      const box = el('div', 'kid-card');
      box.style.cssText = 'max-width:340px;width:100%;display:grid;gap:12px;text-align:center;';
      box.appendChild(el('div', 'word-big', 'Уйти с урока?'));
      const stay = el('button', 'kid-btn', '▶️ Продолжить');
      stay.onclick = () => overlay.remove();
      const leave = el('button', 'kid-btn ghost', '🚪 Выйти');
      leave.onclick = () => location.href = opts.backUrl || '/static/pages/home.html';
      box.appendChild(stay); box.appendChild(leave);
      overlay.appendChild(box);
      document.body.appendChild(overlay);
    };
    const dots = el('div', 'dots');
    top.appendChild(back); top.appendChild(dots);
    const card = el('div', 'kid-card');
    const screen = el('div', '');
    screen.style.cssText = 'display:grid;justify-items:center;gap:4px;';
    card.appendChild(screen);
    container.appendChild(top); container.appendChild(card);

    let data;
    try {
      data = opts.daily
        ? await api('/lesson/daily')
        : await api(`/lesson/unit/${opts.themeId}/${opts.lessonNo}`);
    } catch (e) {
      let msg = 'Ой! Не получилось загрузить урок 😔';
      try { const d = JSON.parse(e.message); if (d.detail) msg = d.detail; } catch (err) {}
      screen.innerHTML = '';
      screen.appendChild(el('div', 'sticker-award', '🦊'));
      screen.appendChild(el('div', 'word-big', msg));
      const home = el('button', 'kid-btn', '🏠 На главную');
      home.style.marginTop = '14px';
      home.onclick = () => location.href = '/static/pages/home.html';
      screen.appendChild(home);
      speakRuBrowser(msg);
      return;
    }

    if (data.completed) {
      screen.appendChild(el('div', 'sticker-award', '✅'));
      screen.appendChild(el('div', 'word-big', 'Задание на сегодня выполнено!'));
      screen.appendChild(el('div', 'stars-row', '⭐'.repeat(data.stars || 1)));
      screen.appendChild(el('div', 'word-small', 'Хочешь ещё? Иди по карте!'));
      const map = el('button', 'kid-btn secondary', '🗺️ На карту');
      map.onclick = () => location.href = '/static/pages/path.html';
      const home = el('button', 'kid-btn', '🏠 На главную');
      home.style.marginTop = '10px';
      home.onclick = () => location.href = '/static/pages/home.html';
      screen.appendChild(map); screen.appendChild(home);
      return;
    }

    const items = data.items || [];
    items.forEach(() => dots.appendChild(document.createElement('i')));
    let idx = 0, correct = 0, total = 0;

    function renderCurrent() {
      [...dots.children].forEach((d, i) => {
        d.className = i < idx ? 'done' : (i === idx ? 'now' : '');
      });
      screen.innerHTML = '';
      if (idx >= items.length) return finish();
      const item = items[idx];
      const renderer = RENDERERS[item.type];
      if (!renderer) { idx++; return renderCurrent(); }
      let doneFired = false; // защита от двойного тапа по «Дальше»
      renderer(item, screen, (res) => {
        if (doneFired) return;
        doneFired = true;
        if (res && res.scored) {
          total++;
          if (res.ok) {
            correct++;
          } else if (!item._requeued) {
            // ошибся — то же задание вернётся в конце урока
            item._requeued = true;
            items.push(item);
            dots.appendChild(document.createElement('i'));
          }
        }
        idx++;
        renderCurrent();
      });
    }

    function showStart() {
      // стартовый жест: разблокирует звук на iOS/Chrome и даёт ребёнку «приготовиться»
      screen.innerHTML = '';
      const icon = el('div', 'sticker-award', data.is_boss ? '👑' : '🦊');
      screen.appendChild(icon);
      screen.appendChild(el('div', 'word-big', data.is_boss ? 'Большая игра!' : 'Начинаем урок!'));
      const go = el('button', 'kid-btn', '▶️ Поехали!');
      go.style.marginTop = '14px';
      go.onclick = () => {
        // тихий прогрев всех аудио-каналов жестом (разблокировка iOS/Chrome) —
        // раньше тут звучало «Молодец!», которое перекрывалось первой карточкой
        const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=';
        [audioEl, ruAudioEl, sfxGood, sfxBad].forEach(a => {
          try {
            a.muted = true;
            const src = a.src; a.src = SILENT;
            const p = a.play(); if (p) p.catch(() => {});
            a.pause(); a.muted = false;
            if (src) a.src = src;
          } catch (e) {}
        });
        renderCurrent();
      };
      screen.appendChild(go);
    }

    async function finish() {
      const payload = {
        kind: opts.daily ? 'daily' : 'unit',
        theme_id: opts.themeId || null,
        lesson_no: opts.lessonNo || null,
        correct, total,
      };
      const result = (await reportComplete(payload)) || { stars: stars_estimate(), sticker: null, streak: 0 };
      function stars_estimate() { return total > 0 && correct / total >= 0.9 ? 3 : (total > 0 && correct / total >= 0.7 ? 2 : 1); }
      screen.innerHTML = '';
      confetti();
      // сначала фанфары, потом голос — не одновременно
      playFx(true).then(() => speakRu(result.stars >= 3 ? 'Молодец! Отлично!' : 'Молодец!'));
      screen.appendChild(el('div', 'word-big', 'Афәрин! 🎉'));
      screen.appendChild(el('div', 'stars-row', '⭐'.repeat(result.stars || 1) + '☆'.repeat(3 - (result.stars || 1))));
      if (total > 0) screen.appendChild(el('div', 'word-small', `Правильно: ${correct} из ${total}`));
      if (result.sticker) {
        screen.appendChild(el('div', 'word-small', 'Новая наклейка!'));
        screen.appendChild(el('div', 'sticker-award', result.sticker));
      }
      if (opts.daily && result.streak) {
        screen.appendChild(el('div', 'word-small', `🔥 Серия: ${result.streak} дн.`));
      }
      const row = el('div', '');
      row.style.cssText = 'display:grid;gap:10px;width:100%;margin-top:16px;';
      const map = el('button', 'kid-btn secondary', '🗺️ На карту');
      map.onclick = () => location.href = '/static/pages/path.html';
      const home = el('button', 'kid-btn', '🏠 На главную');
      home.onclick = () => location.href = '/static/pages/home.html';
      row.appendChild(map); row.appendChild(home);
      screen.appendChild(row);
    }

    showStart();
  }

  window.Lesson = { run, api, playAudio, speakRu, visual, el, confetti };
})();
