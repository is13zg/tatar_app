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
  // Каждый play раньше ходил в сеть: статика отвечала без Cache-Control, и на
  // слабом интернете повторное нажатие 🔊 снова тянуло тот же wav. Теперь файл
  // скачивается один раз, дальше играет из памяти страницы.
  const audioBlobCache = new Map();   // url -> objectURL
  async function audioSrc(url) {
    if (!url || !url.startsWith('/static/')) return url;  // blob: и чужие — как есть
    const hit = audioBlobCache.get(url);
    if (hit) return hit;
    try {
      const r = await fetch(url);
      if (!r.ok) return url;
      const obj = URL.createObjectURL(await r.blob());
      if (audioBlobCache.size >= 200) {   // не копим бесконечно: самый старый на выход
        const oldest = audioBlobCache.keys().next().value;
        URL.revokeObjectURL(audioBlobCache.get(oldest));
        audioBlobCache.delete(oldest);
      }
      audioBlobCache.set(url, obj);
      return obj;
    } catch (e) {
      return url;   // сеть упала — пробуем играть напрямую, как раньше
    }
  }

  function playAudio(url) {
    return new Promise(resolve => {
      if (!url) return resolve();
      // татарское слово главнее: глушим инструкцию, чтобы голоса не накладывались
      try { speechSynthesis.cancel(); } catch (e) {}
      try { ruAudioEl.pause(); } catch (e) {}
      try { audioEl.pause(); audioEl.currentTime = 0; } catch (e) {}
      audioSrc(url).then(src => {
        audioEl.src = src;
        audioEl.onended = () => resolve();
        audioEl.onerror = () => resolve();
        audioEl.play().catch(() => resolve());
      });
      setTimeout(resolve, 10000); // страховка
    });
  }

  // Записанные инструкции (Сбер SaluteSpeech, tools/gen_ru_instructions.py).
  // Если файла нет — фолбэк на браузерный синтез (он для русского звучит приемлемо).
  const INSTR_AUDIO = {
    'Новое слово!': 'novoe_slovo',
    'Собери предложение из слов': 'soberi_predlozhenie',
    'Что в коробке? Нажми!': 'chto_v_korobke',
    'Кто прячется в тени? Нажми!': 'kto_v_teni',
    'Раскрась картинку! Нажимай!': 'raskras_kartinku',
    'Помоги вырасти! Нажимай!': 'pomogi_vyrasti',
    'Лопни пузырь со словом!': 'lopni_puzyr',
    'Покорми Акбая!': 'pokormi_akbaya',
    'Запомни, кто здесь!': 'zapomni_kto',
    'Кто убежал? Найди!': 'kto_ubezhal',
    'Лови только то, что я называю!': 'lovi_tolko',
    'Открывай окошки и запоминай!': 'otkryvaj_okoshki',
    'Что здесь лишнее?': 'chto_lishnee',
    'Найди наоборот!': 'najdi_naoborot',
    'Ответь на вопрос!': 'otvet_na_vopros',
    'Выбери: какой?': 'vyberi_kakoy',
    'Чем это делают?': 'chem_delayut',
    'Один или много?': 'odin_ili_mnogo',
    'Одень Марата по погоде!': 'oden_marata',
    'Где кошка?': 'gde_koshka',
    'Сейчас или уже?': 'seychas_ili_uzhe',
    'Сколько предметов?': 'skolko_predmetov',
    'Почему? Выбери, какой он': 'pochemu_kakoy',
    'Послушай историю': 'poslushay_istoriyu',
    'Ответь на вопрос!': 'otvet_na_vopros',
    'Сейчас будет история из трёх кусочков. Слушай, кто что делает, а потом ответь на вопрос.': 'demo_story',
    'Он не поел.': 'prichina_ne_poel',
    'Он не пил воду.': 'prichina_ne_pil',
    'Он не спал.': 'prichina_ne_spal',
    'Там большая собака.': 'prichina_sobaka',
    'Делает сейчас': 'delaet_seychas',
    'Уже сделал': 'uzhe_sdelal',
    'Кошка на всех картинках одинаковая. Слушай, где она.': 'demo_where',
    'Слушай слово. Если делает сейчас — нажми песочные часы. Если уже сделал — флажок.': 'demo_past',
    'Посчитай предметы. Слушай кнопки и выбери, где названо столько же.': 'demo_count',
    'Я расскажу, что случилось. А ты выбери, какой он.': 'demo_why',
    'Посвети! Кто прячется в темноте?': 'posveti_fonarikom',
    'Повтори цепочку!': 'povtori_cepochku',
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
      ruAudioEl.onended = () => resolve();
      ruAudioEl.onerror = () => {
        if (my === speakToken) {
          missingInstr.add(key); // реальная ошибка загрузки (404/сеть)
          speakRuBrowser(text).then(resolve);
        } else {
          resolve(); // нас просто перебили следующим звуком — файл не виноват
        }
      };
      audioSrc(`/static/voice/ru/${key}.wav`).then(src => {
        if (my !== speakToken) return resolve();   // пока качали, нас перебили
        ruAudioEl.src = src;
        ruAudioEl.play().catch(() => resolve()); // перебили другим звуком — тихо выходим
      });
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

  let lessonPaused = false; // диалог «Уйти с урока?» ставит всё на паузу
  async function waitUnpaused() { while (lessonPaused) await sleep(200); }

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

  // Разовая демонстрация правила для абстрактных упражнений («наоборот», «лишнее»):
  // нечитающему ребёнку метаконцепт надо ПОКАЗАТЬ, а не только назвать словом.
  function introSeen(type) { try { return localStorage.getItem('intro_' + type) === '1'; } catch (e) { return false; } }
  function markIntro(type) { try { localStorage.setItem('intro_' + type, '1'); } catch (e) {} }

  function showExerciseIntro(type, screen) {
    return new Promise(resolve => {
      screen.innerHTML = '';
      const wrap = el('div', ''); wrap.style.cssText = 'display:grid;justify-items:center;gap:12px;text-align:center;';
      if (type === 'opposite') {
        wrap.appendChild(el('div', 'instr', '↔️ Игра «Наоборот»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;align-items:center;gap:16px;';
        const big = el('div', 'emoji', '🔵'); big.style.fontSize = '92px';
        const arr = el('div', '', '↔️'); arr.style.fontSize = '44px';
        const small = el('div', 'emoji', '🔵'); small.style.fontSize = '30px';
        row.appendChild(big); row.appendChild(arr); row.appendChild(small);
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Слышишь слово — ищи наоборот!'));
        speakRuBrowser('Я называю слово, а ты ищи наоборот! Большой — а наоборот маленький.');
      } else if (type === 'story') {
        wrap.appendChild(el('div', 'instr', 'Игра «Послушай историю»'));
        const row = el('div', '');
        row.style.cssText = 'display:flex;gap:14px;align-items:center;';
        ['\u{1F415}', '\u{1F408}', '\u{1F414}'].forEach(e => {
          const d = el('div', '', e);
          d.style.fontSize = '44px';
          row.appendChild(d);
        });
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Три фразы подряд, потом вопрос'));
        speakRu('Сейчас будет история из трёх кусочков. Слушай, кто что делает, а потом ответь на вопрос.');
      } else if (type === 'where') {
        wrap.appendChild(el('div', 'instr', 'Игра «Где кошка?»'));
        const row = el('div', '');
        row.style.cssText = 'display:flex;gap:22px;align-items:flex-end;';
        // те же самые сцены, что и в задании: раньше интро учило горизонтали,
        // а упражнение спрашивало про вертикаль
        [['on', 'өстендә'], ['under', 'астында']].forEach(pair => {
          const c = el('div', '');
          c.style.cssText = 'display:grid;justify-items:center;gap:4px;width:120px;';
          c.appendChild(placeScene({ anchor: '\u{1F6CF}', subject: '\u{1F431}' }, pair[0]));
          c.appendChild(el('div', 'word-small', pair[1]));
          row.appendChild(c);
        });
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Кошка везде одна — слушай, ГДЕ она!'));
        setTimeout(() => sizeScenes(wrap), 0);
        speakRu('Кошка на всех картинках одинаковая. Слушай, где она.');
      } else if (type === 'past') {
        wrap.appendChild(el('div', 'instr', 'Игра «Сейчас или уже?»'));
        const row = el('div', '');
        row.style.cssText = 'display:flex;gap:20px;align-items:center;';
        const a = el('div', '', '\u25B6\uFE0F');
        a.style.fontSize = '48px';
        const t1 = el('div', 'word-small', 'ашый — ест сейчас');
        const b = el('div', '', '\u2705');
        b.style.fontSize = '48px';
        const t2 = el('div', 'word-small', 'ашады — уже поел');
        [a, t1, b, t2].forEach(x => row.appendChild(x));
        wrap.appendChild(row);
        speakRu('Слушай слово. Если делает сейчас — нажми песочные часы. Если уже сделал — флажок.');
      } else if (type === 'count') {
        wrap.appendChild(el('div', 'instr', 'Игра «Сколько предметов?»'));
        const row = el('div', '');
        row.style.cssText = 'display:flex;gap:8px;';
        for (let i = 0; i < 3; i++) {
          const e = el('div', '', '\u{1F34E}');
          e.style.fontSize = '44px';
          row.appendChild(e);
        }
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', '\u00F6\u0447 \u0430\u043B\u043C\u0430 \u2014 \u0442\u0440\u0438 \u044F\u0431\u043B\u043E\u043A\u0430'));
        speakRu('Посчитай предметы. Слушай кнопки и выбери, где названо столько же.');
      } else if (type === 'why') {
        wrap.appendChild(el('div', 'instr', 'Игра «Почему?»'));
        const row = el('div', '');
        row.style.cssText = 'display:flex;gap:16px;align-items:center;';
        const a = el('div', 'word-small', 'Ул ашамады');
        const arr = el('div', '', '\u2192');
        arr.style.fontSize = '34px';
        const b = el('div', '', '\u{1F37D}');
        b.style.fontSize = '48px';
        [a, arr, b].forEach(x => row.appendChild(x));
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Не поел — значит голодный!'));
        speakRuBrowser('Я расскажу, что случилось. А ты выбери, какой он теперь.');
      } else if (type === 'negation') {
        wrap.appendChild(el('div', 'instr', '🚫 Игра «Әйе — Юк»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;gap:18px;align-items:center;';
        const a = el('div', '', '🏊'); a.style.fontSize = '52px';
        const eq = el('div', '', '→'); eq.style.fontSize = '34px';
        const b = el('div', '', '👍 Әйе'); b.style.cssText = 'font-size:22px;font-weight:800;';
        row.appendChild(a); row.appendChild(eq); row.appendChild(b);
        wrap.appendChild(row);
        const row2 = el('div', ''); row2.style.cssText = 'display:flex;gap:18px;align-items:center;';
        const c = el('div', '', '🏃'); c.style.fontSize = '52px';
        const eq2 = el('div', '', '→'); eq2.style.fontSize = '34px';
        const d = el('div', '', '👎 Юк'); d.style.cssText = 'font-size:22px;font-weight:800;';
        row2.appendChild(c); row2.appendChild(eq2); row2.appendChild(d);
        wrap.appendChild(row2);
        wrap.appendChild(el('div', 'word-small', 'Спросят про картинку — отвечай Әйе или Юк'));
        speakRuBrowser('Я спрошу, что он делает. Если на картинке это — жми Әйе. Если другое — жми Юк.');
      } else if (type === 'with_what') {
        wrap.appendChild(el('div', 'instr', '🛠 Игра «Чем это делают»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;gap:16px;align-items:center;';
        ['✍️', '→', '🖊'].forEach((e, i) => { const d = el('div', '', e); d.style.fontSize = i === 1 ? '32px' : '52px'; row.appendChild(d); });
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Слушай вопрос и выбирай нужный предмет'));
        speakRuBrowser('Я спрошу, чем это делают. Выбери нужный предмет!');
      } else if (type === 'alt_question') {
        wrap.appendChild(el('div', 'instr', '🤔 Игра «Какой?»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;gap:20px;align-items:center;';
        const big = el('div', '', '📗'); big.style.fontSize = '62px';
        const or = el('div', '', 'или'); or.style.fontSize = '20px';
        const small = el('div', '', '📄'); small.style.fontSize = '42px';
        row.appendChild(big); row.appendChild(or); row.appendChild(small);
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Услышишь два слова — выбери подходящую картинку'));
        speakRuBrowser('Я назову два слова. Выбери картинку, которая подходит!');
      } else if (type === 'plural') {
        wrap.appendChild(el('div', 'instr', '🔢 Игра «Один или много»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;gap:22px;align-items:center;';
        const one = el('div', '', '🍎'); one.style.fontSize = '54px';
        const many = el('div', '', '🍎🍎🍎'); many.style.fontSize = '34px';
        row.appendChild(one); row.appendChild(many);
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Слушай два слова и выбери, что на картинке'));
        speakRuBrowser('Послушай два слова. Одно про один предмет, другое про много. Выбери подходящее!');
      } else if (type === 'question') {
        wrap.appendChild(el('div', 'instr', '🗣 Игра «Әйе — Юк»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;gap:24px;justify-content:center;';
        const yes = el('div', ''); yes.style.textAlign = 'center';
        yes.appendChild(el('div', '', '👍')).style.fontSize = '54px';
        yes.appendChild(el('div', 'word-big', 'Әйе'));
        yes.appendChild(el('div', 'word-small', 'да'));
        const no = el('div', ''); no.style.textAlign = 'center';
        no.appendChild(el('div', '', '👎')).style.fontSize = '54px';
        no.appendChild(el('div', 'word-big', 'Юк'));
        no.appendChild(el('div', 'word-small', 'нет'));
        row.appendChild(yes); row.appendChild(no);
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Слушай вопрос и отвечай по-татарски!'));
        speakRuBrowser('Я спрашиваю по-татарски! Если да — жми Әйе. Если нет — жми Юк!');
      } else { // odd_one
        wrap.appendChild(el('div', 'instr', '🧐 Игра «Что лишнее»'));
        const row = el('div', ''); row.style.cssText = 'display:flex;gap:12px;';
        ['🍎', '🍐', '🍌', '🚗'].forEach((e, i) => {
          const d = el('div', '', e); d.style.fontSize = '54px';
          if (i === 3) { d.style.transform = 'scale(1.15)'; d.style.filter = 'drop-shadow(0 0 10px #ef4444)'; }
          row.appendChild(d);
        });
        wrap.appendChild(row);
        wrap.appendChild(el('div', 'word-small', 'Три — про одно, а одна лишняя!'));
        speakRuBrowser('Три картинки про одно, а одна лишняя. Найди, что не подходит!');
      }
      const go = el('button', 'kid-btn', 'Понятно! ▶️'); go.style.marginTop = '8px';
      go.onclick = () => { markIntro(type); resolve(); };
      wrap.appendChild(go);
      screen.appendChild(wrap);
    });
  }

  function sentenceLine(w) {
    // предложение с подсветкой целевого слова
    const box = el('div', '');
    box.style.cssText = 'text-align:center;margin-top:10px;background:#fff7ed;border-radius:14px;padding:10px 14px;';
    const line = el('div', '');
    line.style.cssText = 'font-size:20px;font-weight:600;';
    const s = w.sentence_tt;
    const idx = s.toLowerCase().indexOf(w.text_tt.toLowerCase());
    if (idx >= 0) {
      line.appendChild(document.createTextNode(s.slice(0, idx)));
      const b = el('b', '', s.slice(idx, idx + w.text_tt.length));
      b.style.color = '#ea580c';
      line.appendChild(b);
      line.appendChild(document.createTextNode(s.slice(idx + w.text_tt.length)));
    } else {
      line.textContent = s;
    }
    box.appendChild(line);
    if (w.sentence_ru) {
      const ru = el('div', '', w.sentence_ru);
      ru.style.cssText = 'font-size:14px;color:#92400e;margin-top:2px;';
      box.appendChild(ru);
    }
    return box;
  }

  function rCard(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🆕 Новое слово'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(w)); screen.appendChild(vis);
    screen.appendChild(el('div', 'word-big', w.text_tt));
    screen.appendChild(el('div', 'word-small', w.text_ru));
    if (w.sentence_tt) screen.appendChild(sentenceLine(w));
    const row = el('div', ''); row.style.cssText = 'display:flex;gap:12px;align-items:center;margin-top:14px;flex-wrap:wrap;justify-content:center;';
    const play = el('button', 'play-btn', '🔊');
    play.title = 'Слово';
    play.onclick = () => playAudio(w.audio_url);
    row.appendChild(play);
    if (w.sentence_audio_url) {
      const sp = el('button', 'play-btn', '💬');
      sp.title = 'Предложение';
      sp.style.background = '#0ea5e9';
      sp.onclick = () => playAudio(w.sentence_audio_url);
      row.appendChild(sp);
    }
    const next = el('button', 'kid-btn', 'Дальше ➜');
    next.onclick = () => done({ scored: false });
    row.appendChild(next); screen.appendChild(row);
    (async () => {
      await speakThenPlay('Новое слово!', w.audio_url);
      if (w.sentence_audio_url) { await sleep(400); await playAudio(w.sentence_audio_url); }
    })();
  }

  // ---- презентационные мини-игры подачи (уроки 1-2, провал невозможен) ----

  function presenterFooter(w, screen, done) {
    // общий низ: слово + перевод + предложение + «Дальше»
    const twp = el('div', 'word-big', w.text_tt);
    if ((w.text_tt || '').length > 14) twp.style.fontSize = '24px';
    screen.appendChild(twp);
    screen.appendChild(el('div', 'word-small', w.text_ru));
    if (w.sentence_tt) screen.appendChild(sentenceLine(w));
    const row = el('div', ''); row.style.cssText = 'display:flex;gap:12px;align-items:center;margin-top:12px;flex-wrap:wrap;justify-content:center;';
    const play = el('button', 'play-btn', '🔊');
    play.title = 'Слово';
    play.onclick = () => playAudio(w.audio_url);
    row.appendChild(play);
    if (w.sentence_audio_url) {
      const sp = el('button', 'play-btn', '💬');
      sp.title = 'Предложение';
      sp.style.background = '#0ea5e9';
      sp.onclick = () => playAudio(w.sentence_audio_url);
      row.appendChild(sp);
    }
    const next = el('button', 'kid-btn', 'Дальше ➜');
    next.onclick = () => done({ scored: false });
    row.appendChild(next); screen.appendChild(row);
  }

  function rSurpriseBox(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🎁 Что в коробке? Нажми!'));
    const stage = el('div', 'big-visual');
    const box = el('div', '', '🎁');
    box.style.cssText = 'font-size:clamp(90px,30vw,150px);cursor:pointer;animation:shake 1.2s infinite;line-height:1.1;';
    stage.appendChild(box);
    screen.appendChild(stage);
    let opened = false;
    const open = async () => {
      if (opened) return; opened = true;
      stage.innerHTML = '';
      const v = visual(w);
      v.style && (v.style.animation = 'pop .5s');
      stage.appendChild(v);
      confetti();
      audioEl.volume = 1;
      await playAudio(w.audio_url);
      if (w.sentence_audio_url) { await sleep(350); await playAudio(w.sentence_audio_url); }
      presenterFooter(w, screen, done);
    };
    box.onclick = open;
    // приглушённое слово из закрытой коробки — интрига
    (async () => { await speakRu('Что в коробке? Нажми!'); audioEl.volume = 0.35; await playAudio(w.audio_url); audioEl.volume = 1; })();
  }

  function rShadowReveal(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🌑 Кто прячется в тени? Нажми!'));
    const stage = el('div', 'big-visual');
    const v = visual(w);
    v.style.filter = 'brightness(0)';
    v.style.transition = 'filter .7s';
    v.style.cursor = 'pointer';
    stage.appendChild(v);
    screen.appendChild(stage);
    let revealed = false;
    v.onclick = async () => {
      if (revealed) return; revealed = true;
      v.style.filter = 'none';
      await sleep(700);
      await playAudio(w.audio_url);
      presenterFooter(w, screen, done);
    };
    speakThenPlay('Кто прячется в тени? Нажми!', w.audio_url);
  }

  function rColorReveal(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🖌️ Раскрась картинку! Нажимай!'));
    const stage = el('div', 'big-visual');
    const v = visual(w);
    const steps = [1, 0.6, 0.3, 0];
    let step = 0;
    v.style.filter = 'grayscale(1)';
    v.style.transition = 'filter .4s';
    v.style.cursor = 'pointer';
    stage.appendChild(v);
    screen.appendChild(stage);
    let finished = false, busy = false;
    v.onclick = async () => {
      if (finished || busy) return; // звуки строго по очереди
      busy = true;
      step = Math.min(step + 1, steps.length - 1);
      v.style.filter = `grayscale(${steps[step]})`;
      await playAudio(w.audio_url);
      busy = false;
      if (step === steps.length - 1 && !finished) {
        finished = true;
        confetti();
        presenterFooter(w, screen, done);
      }
    };
    speakThenPlay('Раскрась картинку! Нажимай!', w.audio_url);
  }

  function rGrowReveal(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', '🌱 Помоги вырасти! Нажимай!'));
    const stage = el('div', 'big-visual');
    const v = visual(w);
    const scales = [0.3, 0.55, 0.8, 1];
    let step = 0;
    v.style.transform = `scale(${scales[0]})`;
    v.style.transition = 'transform .4s';
    v.style.cursor = 'pointer';
    stage.appendChild(v);
    screen.appendChild(stage);
    let finished = false, busy = false;
    stage.onclick = async () => {
      if (finished || busy) return;
      busy = true;
      step = Math.min(step + 1, scales.length - 1);
      v.style.transform = `scale(${scales[step]})`;
      await playAudio(w.audio_url);
      busy = false;
      if (step === scales.length - 1 && !finished) {
        finished = true;
        confetti();
        presenterFooter(w, screen, done);
      }
    };
    speakThenPlay('Помоги вырасти! Нажимай!', w.audio_url);
  }

  // ---- вторая волна мини-игр ----

  function rBubbles(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🫧 Лопни пузырь со словом!'));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    const tw = el('div', 'word-big', item.text_tt);
    if ((item.text_tt || '').length > 14) tw.style.fontSize = '24px';
    head.appendChild(tw);
    screen.appendChild(head);
    const box = el('div', 'bubble-box'); screen.appendChild(box);
    let locked = false;
    shuffled(item.options).forEach((opt, i) => {
      const b = el('button', 'bubble');
      b.appendChild(visual(opt));
      b.style.left = (6 + (i % 2) * 48 + Math.random() * 8) + '%';
      b.style.top = (4 + Math.floor(i / 2) * 46 + Math.random() * 6) + '%';
      b.style.animationDuration = (2.6 + Math.random() * 1.6) + 's';
      b.style.animationDelay = (Math.random() * 1.2) + 's';
      b.onclick = async () => {
        if (locked) return;
        const ok = opt.id === item.word_id;
        if (!ok) { b.classList.add('bubble-shake'); setTimeout(() => b.classList.remove('bubble-shake'), 500); reportAnswer(item.word_id, false, 'bubbles'); locked = true; feedback(false); await playFx(false); [...box.children].forEach(c => { if (c._id === item.word_id) c.classList.add('bubble-pop'); }); await sleep(600); done({ scored: true, ok: false }); return; }
        locked = true;
        b.classList.add('bubble-pop');
        reportAnswer(item.word_id, true, 'bubbles');
        feedback(true); await playFx(true); await sleep(500);
        done({ scored: true, ok: true });
      };
      b._id = opt.id;
      box.appendChild(b);
    });
    speakThenPlay('Лопни пузырь со словом!', item.audio_url);
  }

  function rFeed(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🐶 Покорми Акбая!'));
    const stage = el('div', ''); stage.style.cssText = 'display:flex;align-items:center;justify-content:center;gap:10px;margin:6px 0;';
    const dog = el('div', '', '🐶');
    dog.style.cssText = 'font-size:clamp(70px,20vw,110px);cursor:pointer;line-height:1.1;';
    dog.onclick = () => playAudio(item.audio_url);
    const bubble = el('div', '', '🔊 ' + item.text_tt);
    bubble.style.cssText = 'background:white;border:3px solid #e5e7eb;border-radius:16px;padding:8px 12px;font-weight:700;font-size:18px;';
    stage.appendChild(dog); stage.appendChild(bubble);
    screen.appendChild(stage);
    const grid = el('div', 'tile-grid'); grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    screen.appendChild(grid);
    let locked = false;
    shuffled(item.options).forEach(opt => {
      const t = el('button', 'tile');
      t.appendChild(visual(opt));
      t.onclick = async () => {
        if (locked) return; locked = true;
        const ok = opt.id === item.word_id;
        reportAnswer(item.word_id, ok, 'feed');
        if (ok) {
          t.classList.add('good');
          dog.textContent = '😋';
          dog.style.transform = 'scale(1.2)';
          feedback(true, 'Тәмле! 🎉'); await playFx(true);
        } else {
          t.classList.add('bad');
          [...grid.children].forEach(c => { if (c._id === item.word_id) c.classList.add('good'); });
          dog.textContent = '🐶';
          feedback(false); await playFx(false);
        }
        await sleep(600);
        done({ scored: true, ok });
      };
      t._id = opt.id;
      grid.appendChild(t);
    });
    speakThenPlay('Покорми Акбая!', item.audio_url);
  }

  function rWhoRan(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🙈 Запомни, кто здесь!'));
    const rowTop = el('div', 'tile-grid'); rowTop.style.gridTemplateColumns = 'repeat(3, 1fr)';
    screen.appendChild(rowTop);
    const tiles = item.shown.map(w => {
      const t = el('div', 'tile');
      t.style.cursor = 'default';
      t.appendChild(visual(w));
      rowTop.appendChild(t);
      return { t, w };
    });
    (async () => {
      await speakRu('Запомни, кто здесь!');
      for (const { t, w } of tiles) {
        t.style.outline = '5px solid #fbbf24';
        await playAudio(w.audio_url);
        t.style.outline = 'none';
        await sleep(150);
      }
      // занавес
      tiles.forEach(({ t }) => t.classList.add('curtain'));
      await sleep(1200);
      tiles.forEach(({ t, w }) => {
        if (w.id === item.missing_id) t.style.visibility = 'hidden';
        t.classList.remove('curtain');
      });
      const instr = screen.querySelector('.instr');
      if (instr) instr.textContent = '🙀 Кто убежал? Найди!';
      await speakRu('Кто убежал? Найди!');
      // тот же вопрос по-татарски: «Кем юк?» / «Нәрсә юк?» — конструкция отсутствия
      if (item.ask_audio) {
        if (instr) instr.textContent = '🙀 ' + item.ask_tt;
        await playAudio(item.ask_audio);
      }
      const rowOpts = el('div', 'tile-grid'); rowOpts.style.gridTemplateColumns = 'repeat(2, 1fr)';
      screen.appendChild(rowOpts);
      let locked = false;
      shuffled(item.options).forEach(opt => {
        const b = el('button', 'tile');
        b.appendChild(visual(opt));
        b.onclick = async () => {
          if (locked) return; locked = true;
          const ok = opt.id === item.missing_id;
          reportAnswer(item.word_id, ok, 'who_ran');
          b.classList.add(ok ? 'good' : 'bad');
          // беглец возвращается
          tiles.forEach(({ t, w }) => { if (w.id === item.missing_id) t.style.visibility = 'visible'; });
          const missing = item.shown.find(w => w.id === item.missing_id);
          feedback(ok); await playFx(ok);
          if (missing) await playAudio(missing.audio_url);
          if (item.yuk_audio) await playAudio(item.yuk_audio);  // «X юк» — закрепляем отсутствие
          await sleep(300);
          done({ scored: true, ok });
        };
        rowOpts.appendChild(b);
      });
    })();
  }

  function rMoles(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🕳️ Лови только: ' + item.text_tt));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:10px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    screen.appendChild(head);
    const field = el('div', 'holes'); screen.appendChild(field);
    const holes = [0, 1, 2, 3].map(() => {
      const h = el('div', 'hole');
      field.appendChild(h);
      return h;
    });
    let hits = 0, mistakes = 0, idx = 0, tappedThis = false;
    async function round() {
      await waitUnpaused(); // пауза диалога выхода — кроты не бегают без ребёнка
      if (idx >= item.seq.length) {
        const ok = hits >= 2 && mistakes <= 1;
        reportAnswer(item.word_id, ok, 'moles');
        feedback(ok); await playFx(ok); await sleep(400);
        done({ scored: true, ok });
        return;
      }
      const step = item.seq[idx];
      const hole = holes[step.hole];
      hole.innerHTML = '';
      const v = visual(step);
      v.classList && v.classList.add('mole-up');
      hole.appendChild(v);
      tappedThis = false;
      hole.onclick = () => {
        if (tappedThis) return; tappedThis = true;
        if (step.is_target) { hits++; hole.classList.add('hole-good'); }
        else { mistakes++; hole.classList.add('hole-bad'); }
        setTimeout(() => hole.classList.remove('hole-good', 'hole-bad'), 350);
        hole.innerHTML = '';
      };
      await sleep(1700);
      if (!tappedThis && step.is_target) mistakes++;  // прозевал цель
      hole.onclick = null;
      hole.innerHTML = '';
      idx++;
      await sleep(350);
      round();
    }
    (async () => {
      await speakRu('Лови только то, что я называю!');
      await playAudio(item.audio_url);
      round();
    })();
  }

  // ---- третья волна мини-игр ----

  function rWindows(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🪟 Открывай окошки и запоминай!'));
    const grid = el('div', 'tile-grid'); screen.appendChild(grid);
    const target = item.items.find(w => w.id === item.word_id);
    let phase = 'expo'; // expo → recall
    let locked = false;
    const cells = item.items.map(w => {
      const c = el('button', 'tile windows-cell');
      const v = visual(w);
      const cover = el('div', 'shutter', '🪟');
      c.appendChild(v); c.appendChild(cover);
      c.onclick = async () => {
        if (locked) return;
        if (phase === 'expo') {
          if (!cover.classList.contains('shutter-open')) {
            cover.classList.add('shutter-open');
            await playAudio(w.audio_url);
            if (cells.every(x => x.cover.classList.contains('shutter-open'))) {
              // всё открыто и услышано — закрываем и спрашиваем
              locked = true;
              await sleep(700);
              cells.forEach(x => x.cover.classList.remove('shutter-open'));
              await sleep(500);
              const instr = screen.querySelector('.instr');
              if (instr) instr.textContent = '🔍 Где это слово? Слушай!';
              await playAudio(target.audio_url);
              phase = 'recall';
              locked = false;
            }
          }
          return;
        }
        // recall: тап по окну = ответ
        locked = true;
        const ok = w.id === item.word_id;
        reportAnswer(item.word_id, ok, 'windows');
        cover.classList.add('shutter-open');
        c.classList.add(ok ? 'good' : 'bad');
        if (!ok) {
          cells.forEach(x => { if (x.w.id === item.word_id) { x.cover.classList.add('shutter-open'); x.c.classList.add('good'); } });
        }
        feedback(ok); await playFx(ok);
        await playAudio(target.audio_url);
        done({ scored: true, ok });
      };
      grid.appendChild(c);
      return { c, cover, w };
    });
    speakRu('Открывай окошки и запоминай!');
  }

  function rFlashlight(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🔦 Посвети! Кто прячется в темноте?'));
    const stage = el('div', 'flash-stage');
    const v = visual(item.target);
    stage.appendChild(v);
    const dark = el('div', 'flash-dark');
    stage.appendChild(dark);
    screen.appendChild(stage);
    let moves = 0;
    const setLight = (e) => {
      const r = stage.getBoundingClientRect();
      const x = ((e.touches ? e.touches[0].clientX : e.clientX) - r.left);
      const y = ((e.touches ? e.touches[0].clientY : e.clientY) - r.top);
      dark.style.background = `radial-gradient(circle 64px at ${x}px ${y}px, rgba(0,0,0,0) 0, rgba(15,23,42,0.55) 55px, rgba(15,23,42,0.97) 90px)`;
      moves++;
      if (moves === 24) showOptions(); // поисследовал — пора отвечать
    };
    dark.addEventListener('pointermove', setLight);
    dark.addEventListener('pointerdown', setLight);
    let shown = false;
    function showOptions() {
      if (shown) return; shown = true;
      const grid = el('div', 'tile-grid'); grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
      screen.appendChild(grid);
      let locked = false;
      shuffled(item.options).forEach(opt => {
        const t = el('button', 'tile');
        t.appendChild(visual(opt));
        t.onclick = async () => {
          if (locked) return; locked = true;
          const ok = opt.id === item.word_id;
          reportAnswer(item.word_id, ok, 'flashlight');
          t.classList.add(ok ? 'good' : 'bad');
          dark.style.transition = 'opacity .6s';
          dark.style.opacity = '0'; // свет включается
          if (!ok) [...grid.children].forEach(c => { if (c._id === item.word_id) c.classList.add('good'); });
          feedback(ok); await playFx(ok);
          await playAudio(item.target.audio_url);
          done({ scored: true, ok });
        };
        t._id = opt.id;
        grid.appendChild(t);
      });
      grid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setTimeout(showOptions, 9000); // страховка: варианты появятся сами
    speakRu('Посвети! Кто прячется в темноте?');
  }

  function rChain(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🎶 Повтори цепочку!'));
    const grid = el('div', 'tile-grid'); grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    screen.appendChild(grid);
    const tiles = item.items.map(w => {
      const t = el('button', 'tile');
      t.appendChild(visual(w));
      grid.appendChild(t);
      return { t, w };
    });
    let expecting = 0, tries = 0, playing = true, locked = false;
    async function playChain() {
      playing = true;
      await sleep(500);
      for (const idx of item.chain) {
        const { t, w } = tiles[idx];
        t.style.outline = '6px solid #fbbf24';
        await playAudio(w.audio_url);
        t.style.outline = 'none';
        await sleep(200);
      }
      playing = false;
    }
    tiles.forEach(({ t, w }, i) => {
      t.onclick = async () => {
        if (playing || locked) return;
        playAudio(w.audio_url);
        if (i === item.chain[expecting]) {
          t.classList.add('good'); setTimeout(() => t.classList.remove('good'), 350);
          expecting++;
          if (expecting === item.chain.length) {
            locked = true;
            const ok = tries === 0;
            reportAnswer(item.word_id, ok, 'chain');
            feedback(true); await playFx(true); await sleep(300);
            done({ scored: true, ok });
          }
        } else {
          t.classList.add('bad'); setTimeout(() => t.classList.remove('bad'), 350);
          tries++;
          expecting = 0;
          if (tries >= 2) {
            locked = true;
            reportAnswer(item.word_id, false, 'chain');
            feedback(false); await playFx(false); await sleep(300);
            done({ scored: true, ok: false });
          } else {
            await playFx(false);
            playChain(); // ещё раз показываем цепочку
          }
        }
      };
    });
    (async () => { await speakRu('Повтори цепочку!'); playChain(); })();
  }

  function rBuildSentence(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🧱 Собери предложение из слов'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(item)); screen.appendChild(vis);
    const playRow = el('div', ''); playRow.style.cssText = 'display:flex;justify-content:center;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    playRow.appendChild(play); screen.appendChild(playRow);

    const slots = el('div', 'slots'); screen.appendChild(slots);
    const tray = el('div', 'letters'); tray.style.flexWrap = 'wrap'; screen.appendChild(tray);
    const checkBtn = el('button', 'kid-btn', '✔ Готово');
    checkBtn.style.marginTop = '10px';
    screen.appendChild(checkBtn);

    const placed = []; // {tile, btn}
    const slotEls = item.tokens.map(() => {
      const s = el('div', 'slot', '');
      s.style.cssText = 'min-width:64px;width:auto;padding:0 10px;font-size:20px;';
      slots.appendChild(s);
      return s;
    });

    function refresh() {
      slotEls.forEach((s, i) => {
        s.textContent = placed[i] ? placed[i].tile.text : '';
        s.classList.toggle('filled', !!placed[i]);
      });
      checkBtn.disabled = placed.length !== item.tokens.length;
    }

    let locked = false;
    item.tiles.forEach(tile => {
      const b = el('button', 'letter-tile', tile.text);
      b.style.cssText = 'width:auto;min-width:64px;padding:0 12px;font-size:19px;height:52px;';
      b.onclick = () => {
        if (locked) return;
        playAudio(tile.audio_url);
        if (b.dataset.used === '1') return;
        if (placed.length >= item.tokens.length) return;
        b.dataset.used = '1'; b.style.opacity = '.35';
        placed.push({ tile, btn: b });
        refresh();
      };
      tray.appendChild(b);
    });

    // тап по заполненному слоту — вернуть слово в лоток
    slotEls.forEach((s, i) => {
      s.onclick = () => {
        if (locked || !placed[i]) return;
        placed[i].btn.dataset.used = ''; placed[i].btn.style.opacity = '1';
        placed.splice(i, 1);
        refresh();
      };
    });

    checkBtn.onclick = async () => {
      if (locked || placed.length !== item.tokens.length) return;
      locked = true;
      const ok = placed.every((p, i) => p.tile.text.toLowerCase() === item.tokens[i].toLowerCase());
      reportAnswer(item.word_id, ok, 'build_sentence');
      if (!ok) {
        // показать правильный порядок и озвучить предложение
        slotEls.forEach((s, i) => { s.textContent = item.tokens[i]; s.classList.add('filled'); s.style.borderColor = '#16a34a'; });
      }
      feedback(ok); await playFx(ok);
      await playAudio(item.audio_url);
      await sleep(400);
      done({ scored: true, ok });
    };

    refresh();
    speakThenPlay('Собери предложение из слов', item.audio_url);
  }

  async function rPickImage(item, screen, done) {
    if (item.opposite_mode && !introSeen('opposite')) await showExerciseIntro('opposite', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', item.opposite_mode ? '↔️ Найди наоборот!' : '👂 Послушай и найди картинку'));
    // якорь: картинка исходного слова, от которого ищем противоположность (ребёнку нужна опора)
    if (item.opposite_mode && item.source) {
      const anchor = el('div', ''); anchor.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:2px;margin-bottom:6px;';
      const av = el('div', 'big-visual'); av.style.cssText = 'width:110px;height:110px;'; av.appendChild(visual(item.source));
      anchor.appendChild(av);
      const lab = el('div', 'word-small', '↔️ наоборот'); lab.style.color = '#8b5cf6';
      anchor.appendChild(lab);
      screen.appendChild(anchor);
    }
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:14px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    const tw = el('div', 'word-big', item.text_tt);
    if ((item.text_tt || '').length > 14) tw.style.fontSize = '24px'; // предложение — шрифт меньше
    head.appendChild(tw);
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
          if (item.opposite_mode) { await sleep(400); await playAudio(item.audio_url); } // переслушать исходное слово
        }
        feedback(ok); await playFx(ok); await sleep(700);
        done({ scored: true, ok });
      };
      t._id = opt.id;
      grid.appendChild(t);
    });
    speakThenPlay(item.opposite_mode ? 'Найди наоборот!' : 'Послушай и найди картинку', item.audio_url);
  }

  async function rOddOne(item, screen, done) {
    if (!introSeen('odd_one')) await showExerciseIntro('odd_one', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', '🧐 Что здесь лишнее?'));
    const grid = el('div', 'tile-grid'); screen.appendChild(grid);
    const hint = el('div', 'word-small', '👂 Слушай…'); hint.style.marginTop = '8px'; screen.appendChild(hint);
    let locked = false, expoDone = false;
    const tiles = shuffled(item.options).map(opt => {
      const t = el('button', 'tile');
      t.style.opacity = '.4'; // во время прослушивания плитки приглушены — тап пока не работает
      t.appendChild(visual(opt));
      t.onclick = async () => {
        if (locked || !expoDone) return;
        locked = true;
        const ok = opt.id === item.word_id;
        reportAnswer(item.word_id, ok, 'odd_one');
        t.classList.add(ok ? 'good' : 'bad');
        if (!ok) [...grid.children].forEach(c => { if (c._id === item.word_id) c.classList.add('good'); });
        feedback(ok); await playFx(ok); await sleep(500);
        done({ scored: true, ok });
      };
      t._id = opt.id;
      grid.appendChild(t);
      return { t, opt };
    });
    // сначала все четыре слова называются по очереди (плитки приглушены), потом — сигнал «твой ход»
    async function runExposure(first) {
      await waitUnpaused();
      await speakRu('Что здесь лишнее?');
      for (const { t, opt } of tiles) {
        await waitUnpaused();
        t.style.outline = '5px solid #fbbf24'; if (first) t.style.opacity = '1';
        await playAudio(opt.audio_url);
        t.style.outline = 'none'; if (first) t.style.opacity = '.4';
        await sleep(150);
      }
      if (first) {
        expoDone = true;
        tiles.forEach(({ t }) => {
          t.style.opacity = '1';
          try { t.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.06)' }, { transform: 'scale(1)' }], { duration: 420 }); } catch (e) {}
        });
        hint.textContent = '👆 Нажми лишнее!';
        replay.style.display = '';
        speakRuBrowser('Нажми лишнее!');
      }
    }
    const replay = el('button', 'play-btn small', '🔊'); replay.style.cssText = 'margin-top:8px;display:none;';
    replay.onclick = () => { if (expoDone && !locked) runExposure(false); };
    screen.appendChild(replay);
    runExposure(true);
  }

  function rYesNo(item, screen, done) {
    screen.appendChild(el('div', 'instr', '🤔 Это правильная картинка?'));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    const tw2 = el('div', 'word-big', item.text_tt);
    if ((item.text_tt || '').length > 14) tw2.style.fontSize = '24px';
    head.appendChild(tw2);
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

  async function rQuestion(item, screen, done) {
    // вопрос по-татарски («Бу песиме?») — ответ тоже по-татарски: Әйе/Юк
    if (!introSeen('question')) await showExerciseIntro('question', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', '🗣 Ответь: Әйе или Юк!'));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    const tw = el('div', 'word-big', item.text_tt);
    if ((item.text_tt || '').length > 14) tw.style.fontSize = '24px';
    head.appendChild(tw);
    screen.appendChild(head);
    const vis = el('div', 'big-visual'); vis.appendChild(visual(item.shown)); screen.appendChild(vis);
    const row = el('div', 'yn-row');
    let locked = false;
    const answer = async (saidYes) => {
      if (locked) return; locked = true;
      const ok = saidYes === item.is_match;
      reportAnswer(item.word_id, ok, 'question');
      await playAudio(saidYes ? item.aye_audio : item.yuk_audio); // ребёнок «говорит» свой ответ
      feedback(ok); await playFx(ok);
      if (!item.is_match) {
        // обучающая поправка: «Бу X түгел» + имя того, кто на картинке
        if (item.neg_audio) await playAudio(item.neg_audio);
        if (item.shown_audio) await playAudio(item.shown_audio);
      }
      await sleep(400);
      done({ scored: true, ok });
    };
    const yes = el('button', 'kid-btn yn-yes', '👍 Әйе');
    const no = el('button', 'kid-btn yn-no', '👎 Юк');
    yes.onclick = () => answer(true);
    no.onclick = () => answer(false);
    row.appendChild(yes); row.appendChild(no); screen.appendChild(row);
    speakThenPlay('Ответь на вопрос!', item.audio_url);
  }

  async function rAltQuestion(item, screen, done) {
    if (!introSeen('alt_question')) await showExerciseIntro('alt_question', screen);
    screen.innerHTML = '';
    // «Пәлтә калынмы, юкамы?» — две картинки-антонима, выбираем верный признак
    screen.appendChild(el('div', 'instr', '🤔 Выбери: какой?'));
    if (item.source) {   // предмет, про который вопрос — иначе задача без референта
      const anchor = el('div', 'big-visual');
      anchor.style.cssText = 'min-height:110px;';
      const av = el('div', ''); av.style.cssText = 'width:110px;height:110px;display:grid;place-items:center;';
      av.appendChild(visual(item.source));
      anchor.appendChild(av);
      screen.appendChild(anchor);
    }
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:10px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    const tw = el('div', 'word-big', item.text_tt);
    if ((item.text_tt || '').length > 14) tw.style.fontSize = '22px';
    head.appendChild(tw);
    screen.appendChild(head);
    const grid = el('div', 'tile-grid'); screen.appendChild(grid);
    let locked = false;
    shuffled(item.options).forEach(opt => {
      const t = el('button', 'tile');
      t.appendChild(visual(opt));
      t.onclick = async () => {
        if (locked) return; locked = true;
        const ok = opt.id === item.word_id;
        reportAnswer(item.word_id, ok, 'alt_question');
        t.classList.add(ok ? 'good' : 'bad');
        if (!ok) [...grid.children].forEach(c => { if (c._id === item.word_id) c.classList.add('good'); });
        feedback(ok); await playFx(ok);
        const right = item.options.find(o => o.id === item.word_id);
        if (right && right.audio_url) await playAudio(right.audio_url); // подтверждаем верный признак словом
        await sleep(400);
        done({ scored: true, ok });
      };
      t._id = opt.id;
      grid.appendChild(t);
    });
    speakThenPlay('Выбери: какой?', item.audio_url);
  }

  function rDress(item, screen, done) {
    // «Одень Марата»: набираем подходящую по погоде одежду; каждая вещь озвучивается фразой
    screen.appendChild(el('div', 'instr', `${item.scene.emoji} ${item.scene.title_ru}`));
    const hero = el('div', ''); hero.style.cssText = 'font-size:64px;text-align:center;line-height:1;';
    hero.textContent = '🧒';
    screen.appendChild(hero);
    const worn = el('div', ''); worn.style.cssText = 'font-size:30px;text-align:center;min-height:38px;letter-spacing:4px;';
    screen.appendChild(worn);
    const grid = el('div', 'tile-grid'); grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    screen.appendChild(grid);
    let got = 0, mistakes = 0, locked = false;
    shuffled(item.options).forEach(opt => {
      const t = el('button', 'tile');
      t.appendChild(visual(opt));
      t.onclick = async () => {
        if (locked || t.dataset.used === '1') return;
        if (opt.right) {
          t.dataset.used = '1';
          t.classList.add('good');
          t.style.opacity = '.5';
          worn.textContent += opt.emoji || '👕';
          got++;
          await playAudio(opt.audio_url);
          if (opt.phrase_audio) await playAudio(opt.phrase_audio);  // «Марат чалбар кия»
          if (got >= item.need) {
            locked = true;
            hero.textContent = '🧑‍🦱';
            feedback(true, 'Афәрин! 🎉'); await playFx(true);
            await sleep(500);
            done({ scored: true, ok: mistakes === 0 });
          }
        } else {
          mistakes++;
          t.classList.add('bad');
          feedback(false); await playFx(false);
          setTimeout(() => t.classList.remove('bad'), 500);
        }
      };
      grid.appendChild(t);
    });
    speakRu('Одень Марата по погоде!');
  }

  async function rPlural(item, screen, done) {
    if (!introSeen('plural')) await showExerciseIntro('plural', screen);
    screen.innerHTML = '';
    // «Один или много?»: слушаем две формы и выбираем ту, что подходит картинке
    screen.appendChild(el('div', 'instr', '🔢 Один или много?'));
    const vis = el('div', 'big-visual');
    const img = document.createElement('img');
    img.src = item.image_url; img.alt = '';
    vis.appendChild(img);
    screen.appendChild(vis);
    const row = el('div', ''); row.style.cssText = 'display:flex;gap:14px;justify-content:center;margin-top:12px;flex-wrap:wrap;';
    screen.appendChild(row);
    let locked = false, picked = null;
    const check = el('button', 'kid-btn', '✔ Готово');
    check.style.marginTop = '12px';
    check.disabled = true;
    shuffled(item.options).forEach(opt => {
      const b = el('button', 'kid-btn secondary', '🔊');
      b.style.cssText = 'min-width:120px;font-size:26px;';
      b.onclick = () => {
        if (locked) return;
        playAudio(opt.audio_url);            // сначала слушаем, потом выбираем
        picked = opt;
        [...row.children].forEach(c => c.classList.remove('chosen'));
        b.classList.add('chosen');
        b.style.outline = '4px solid var(--accent)';
        [...row.children].forEach(c => { if (c !== b) c.style.outline = 'none'; });
        check.disabled = false;
      };
      row.appendChild(b);
    });
    check.onclick = async () => {
      if (locked || !picked) return;
      locked = true;
      const ok = (picked.key === 'many') === item.many;
      reportAnswer(item.word_id, ok, 'plural');
      feedback(ok); await playFx(ok);
      const right = item.options.find(o => (o.key === 'many') === item.many);
      if (right) await playAudio(right.audio_url);   // подтверждаем верную форму
      await sleep(400);
      done({ scored: true, ok });
    };
    screen.appendChild(check);
    speakThenPlay('Один или много?', null);
  }

  // ---------- форматы выше уровня слова ----------
  // Общее у всех четырёх: узнать предмет на картинке недостаточно, надо
  // расслышать послелог, форму времени, число или связать событие с состоянием.

  // Кот и опора одни и те же во всех вариантах — различается только положение,
  // поэтому сцену рисуем CSS-ом, а не картинкой.
  // Позиции заданы в ПРОЦЕНТАХ плитки, а не в пикселях: плитка тянется сеткой,
  // и хардкод 108px обрезал кошку нижней кромкой (у «астында» срезало 28%).
  // Соседние позиции разведены на 24% высоты — это примерно рост самой кошки.
  // «Артында» больше не полупрозрачная (opacity в приложении уже значит
  // «вариант отключён»), её закрывает второй, обрезанный экземпляр опоры.
  const PLACE_CSS = {
    on:     'left:50%;top:14%;transform:translate(-50%,-50%);z-index:1;',
    behind: 'left:50%;top:38%;transform:translate(-50%,-50%) scale(.86);z-index:1;',
    in:     'left:50%;top:52%;transform:translate(-50%,-50%) scale(.55);z-index:3;',
    front:  'left:50%;top:62%;transform:translate(-50%,-50%) scale(1.15);z-index:3;',
    under:  'left:50%;top:86%;transform:translate(-50%,-50%);z-index:1;',
    near:   'left:80%;top:52%;transform:translate(-50%,-50%);z-index:3;',
  };

  function placeScene(item, pos) {
    // Опора рисуется ДВАЖДЫ: нижний слой целиком, верхний обрезан по низу.
    // Кошка лежит между ними, поэтому в позиции «артында» её реально закрывает
    // кровать, а не имитирует бледность (эмодзи-глиф сам ничего не перекрывает).
    const box = el('div', 'place-scene');
    box.style.cssText = 'position:relative;width:100%;aspect-ratio:1;';
    const anchorCss = 'position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);line-height:1;';
    const back = el('div', 'anc', item.anchor);
    back.style.cssText = anchorCss + 'z-index:0;';
    box.appendChild(back);
    const subj = el('div', 'sub', item.subject);
    subj.style.cssText = 'position:absolute;line-height:1;' + (PLACE_CSS[pos] || PLACE_CSS.near);
    box.appendChild(subj);
    const front = el('div', 'anc', item.anchor);
    front.style.cssText = anchorCss + 'z-index:2;clip-path:inset(42% 0 0 0);';
    box.appendChild(front);
    box._parts = { anchors: [back, front], subj: subj };
    return box;
  }

  // Размеры задаём в пикселях от фактической ширины плитки: проценты в
  // font-size считаются от шрифта родителя, а не от блока, и кошка выходила
  // четырёхпиксельной. Пересчитываем после вставки в документ и на поворот.
  function sizeScenes(root) {
    const scenes = [...root.querySelectorAll('.place-scene')];
    const apply = () => scenes.forEach(box => {
      const w = box.getBoundingClientRect().width;
      if (!w || !box._parts) return;
      box._parts.anchors.forEach(a => { a.style.fontSize = Math.round(w * 0.66) + 'px'; });
      box._parts.subj.style.fontSize = Math.round(w * 0.34) + 'px';
    });
    requestAnimationFrame(apply);
    if (!sizeScenes._bound) {
      sizeScenes._bound = true;
      window.addEventListener('resize', () => {
        document.querySelectorAll('.place-scene').forEach(b => {
          const w = b.getBoundingClientRect().width;
          if (!w || !b._parts) return;
          b._parts.anchors.forEach(a => { a.style.fontSize = Math.round(w * 0.66) + 'px'; });
          b._parts.subj.style.fontSize = Math.round(w * 0.34) + 'px';
        });
      });
    }
  }



  // Рамку красим и классом, и явно. Класс .tile.good/.bad в этих двух форматах
  // почему-то не перебивал серую рамку .tile, хотя в pick_image с теми же
  // классами перебивает; причину в CSS найти не удалось, а ребёнок обязан
  // видеть, где верный ответ — это единственный обучающий момент задания.
  function markTile(cell, ok) {
    cell.classList.add(ok ? 'good' : 'bad');
    // литералы, а не var(): подстановка переменной в этих плитках почему-то
    // не срабатывала для --good, хотя --bad подставлялась (значения те же,
    // что в kid.css); разбираться дальше дороже, чем задать цвет прямо
    cell.style.borderColor = ok ? '#16a34a' : '#ef4444';
  }

  async function rWhere(item, screen, done) {
    if (!introSeen('where')) await showExerciseIntro('where', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', 'Где кошка?'));
    const head = el('div', '');
    head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:10px;';
    const play = el('button', 'play-btn small', '\u{1F50A}');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    screen.appendChild(head);
    const grid = el('div', 'tile-grid');
    let locked = false;
    item.options.forEach(opt => {
      const cell = el('button', 'tile');
      // своя картинка ситуации, если владелец её загрузил; иначе рисуем сцену
      if (item.drawn && opt.image_url) {
        const im = document.createElement('img');
        im.src = opt.image_url; im.alt = '';
        cell.appendChild(im);
      } else {
        cell.appendChild(placeScene(item, opt.pos));
      }
      cell.onclick = async () => {
        if (locked) return;
        locked = true;
        const ok = opt.id === item.answer_id;
        reportAnswer(item.word_id, ok, 'where');
        markTile(cell, ok);
        feedback(ok);
        await playFx(ok);
        if (!ok) {
          const right = [...grid.children][item.options.findIndex(o => o.id === item.answer_id)];
          if (right) markTile(right, true);
          await playAudio(item.audio_url);
        }
        await sleep(500);
        done({ scored: true, ok });
      };
      grid.appendChild(cell);
    });
    screen.appendChild(grid);
    sizeScenes(screen);
    speakThenPlay('Где кошка?', item.audio_url);
  }

  async function rPast(item, screen, done) {
    if (!introSeen('past')) await showExerciseIntro('past', screen);
    screen.innerHTML = '';
    // Ребёнок не читает, поэтому «сейчас» и «уже» — иконки, разница только на слух
    screen.appendChild(el('div', 'instr', 'Сейчас или уже?'));
    const head = el('div', '');
    head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '\u{1F50A}');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    screen.appendChild(head);
    const vis = el('div', 'big-visual');
    vis.appendChild(visual(item));
    screen.appendChild(vis);
    const row = el('div', 'yn-row');
    let locked = false;
    const buttons = [['present', '\u23F3', 'Делает сейчас'], ['past', '\u{1F3C1}', 'Уже сделал']];
    buttons.forEach(pair => {
      const key = pair[0], icon = pair[1], ru = pair[2];
      // обе кнопки одного веса: оранжевая primary читалась как «этот ответ главный»
      const b = el('button', 'kid-btn secondary', icon);
      b.style.cssText = 'min-width:130px;font-size:34px;';
      b.title = ru;
      b.onclick = async () => {
        if (locked) return;
        locked = true;
        const ok = key === item.answer;
        reportAnswer(item.word_id, ok, 'past');
        feedback(ok);
        await playFx(ok);
        if (!ok) {
          await speakRu(item.answer === 'past' ? 'Уже сделал' : 'Делает сейчас');
          await sleep(800);
        }
        await playAudio(item.audio_url);
        await sleep(400);
        done({ scored: true, ok });
      };
      row.appendChild(b);
    });
    screen.appendChild(row);
    speakThenPlay('Сейчас или уже?', item.audio_url);
  }

  async function rCount(item, screen, done) {
    if (!introSeen('count')) await showExerciseIntro('count', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', 'Сколько предметов?'));
    const head = el('div', '');
    head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
    const play = el('button', 'play-btn small', '\u{1F50A}');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    screen.appendChild(head);
    // N одинаковых предметов: считать надо их, картинка у всех одна и та же
    const heap = el('div', '');
    // без nowrap пять предметов на 320px разваливались на 3+2, а считать
    // «вразбежку» дошкольнику заметно труднее, чем ряд
    heap.style.cssText = 'display:flex;gap:8px;flex-wrap:nowrap;justify-content:center;margin:10px 0;';
    for (let i = 0; i < item.n; i++) {
      const one = el('div', '');
      one.style.cssText = 'width:min(72px, calc((100% - 40px) / ' + item.n + '));aspect-ratio:1;' +
        'flex:0 0 auto;display:flex;align-items:center;justify-content:center;';
      if (item.image_url) {
        const im = document.createElement('img');
        im.src = item.image_url;
        im.alt = '';
        im.style.cssText = 'max-width:100%;max-height:100%;';
        one.appendChild(im);
      } else {
        one.textContent = item.emoji || '\u2753';
        one.style.fontSize = '52px';
      }
      heap.appendChild(one);
    }
    screen.appendChild(heap);
    const row = el('div', '');
    row.style.cssText = 'display:flex;gap:12px;justify-content:center;flex-wrap:nowrap;width:100%;';
    let locked = false, picked = null;
    const check = el('button', 'kid-btn', '\u2714 Готово');
    check.style.marginTop = '12px';
    check.disabled = true;
    item.options.forEach(opt => {
      const b = el('button', 'kid-btn secondary', '\u{1F50A}');
      b.style.cssText = 'flex:1 1 0;width:auto;min-width:80px;font-size:26px;';
      b.onclick = () => {
        if (locked) return;
        playAudio(opt.audio_url);          // сначала слушаем связку «число + предмет»
        picked = opt;
        [...row.children].forEach(c => { c.style.outline = 'none'; });
        b.style.outline = '4px solid var(--accent)';
        check.disabled = false;
      };
      row.appendChild(b);
    });
    check.onclick = async () => {
      if (locked || !picked) return;
      locked = true;
      const ok = picked.n === item.answer;
      reportAnswer(item.word_id, ok, 'count');
      feedback(ok);
      await playFx(ok);
      const right = item.options.find(o => o.n === item.answer);
      if (right) await playAudio(right.audio_url);
      await sleep(400);
      done({ scored: true, ok });
    };
    screen.appendChild(row);
    screen.appendChild(check);
    speakThenPlay('Сколько предметов?', item.audio_url);
  }

  async function rWhy(item, screen, done) {
    if (!introSeen('why')) await showExerciseIntro('why', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', 'Почему? Какой он?'));
    const head = el('div', '');
    head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:10px;';
    const play = el('button', 'play-btn small', '\u{1F50A}');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    screen.appendChild(head);
    const grid = el('div', 'tile-grid');
    let locked = false;
    item.options.forEach(opt => {
      const cell = el('button', 'tile');
      cell.appendChild(visual(opt));
      cell.onclick = async () => {
        if (locked) return;
        locked = true;
        const ok = opt.id === item.answer_id;
        reportAnswer(item.word_id, ok, 'why');
        markTile(cell, ok);
        feedback(ok);
        await playFx(ok);
        if (!ok) {
          const right = [...grid.children][item.options.findIndex(o => o.id === item.answer_id)];
          if (right) markTile(right, true);
        }
        await sleep(500);
        done({ scored: true, ok });
      };
      grid.appendChild(cell);
    });
    screen.appendChild(grid);
    // сначала по-русски, что случилось, потом та же фраза по-татарски:
    // половина причин построена на отрицании, без подводки они понимаются наоборот
    (async () => {
      await speakRu('Почему? Выбери, какой он');
      if (item.cause_ru) { await speakRu(item.cause_ru); await sleep(120); }
      await playAudio(item.audio_url);
    })();
  }

  async function rStory(item, screen, done) {
    if (!introSeen('story')) await showExerciseIntro('story', screen);
    screen.innerHTML = '';
    screen.appendChild(el('div', 'instr', 'Послушай историю'));

    // Карточки намеренно мелкие: их четыре, и рядом должен помещаться вопрос
    // с вариантами. Крупные картинки занимали весь экран и заставляли скроллить.
    const row = el('div', '');
    row.style.cssText = 'display:flex;gap:6px;justify-content:center;align-items:flex-start;margin:6px 0 10px;';
    const cards = item.parts.map(p => {
      const c = el('div', '');
      c.style.cssText = 'flex:1 1 0;max-width:84px;display:grid;justify-items:center;gap:3px;' +
        'padding:4px;border-radius:12px;border:3px solid transparent;transition:border-color .2s,transform .2s;';
      const box = el('div', '');
      box.style.cssText = 'width:100%;aspect-ratio:1;display:flex;align-items:center;justify-content:center;overflow:hidden;';
      box.appendChild(visual(p));
      c.appendChild(box);
      const t = el('div', 'word-small', p.text_tt);
      t.style.cssText = 'font-size:11px;line-height:1.1;text-align:center;';
      c.appendChild(t);
      row.appendChild(c);
      return c;
    });
    screen.appendChild(row);

    const again = el('button', 'kid-btn secondary', '\u{1F50A} Ещё раз');
    const go = el('button', 'kid-btn', '\u25B6\uFE0F Вопрос');
    go.disabled = true;
    const btns = el('div', '');
    btns.style.cssText = 'display:flex;gap:12px;justify-content:center;flex-wrap:wrap;';
    btns.appendChild(again);
    btns.appendChild(go);
    screen.appendChild(btns);

    // Читаем подряд, подсвечивая ту карточку, о которой идёт речь: связь
    // «эта фраза — про этого героя» должна быть видна, а не выводиться.
    let telling = false;
    const tell = async () => {
      if (telling) return;
      telling = true;
      again.disabled = true;
      for (let i = 0; i < item.parts.length; i++) {
        cards.forEach(c => { c.style.borderColor = 'transparent'; c.style.transform = 'none'; });
        cards[i].style.borderColor = 'var(--accent)';
        cards[i].style.transform = 'scale(1.06)';
        await playAudio(item.parts[i].audio_url);
        await sleep(240);
      }
      cards.forEach(c => { c.style.borderColor = 'transparent'; c.style.transform = 'none'; });
      telling = false;
      again.disabled = false;
      go.disabled = false;
    };
    again.onclick = tell;

    // Два вопроса подряд про разных героев. Звезда — за оба: одна удача
    // на четырёх вариантах не должна засчитываться как понимание.
    let qi = 0, correct = 0;
    const zone = el('div', '');
    const askNext = async () => {
      zone.innerHTML = '';
      const q = item.questions[qi];
      const label = el('div', 'instr', 'Вопрос ' + (qi + 1) + ' из ' + item.questions.length);
      zone.appendChild(label);
      const head = el('div', '');
      head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:8px;';
      const play = el('button', 'play-btn small', '\u{1F50A}');
      play.onclick = () => playAudio(q.audio_url);
      head.appendChild(play);
      head.appendChild(el('div', 'word-big', q.text_tt));
      zone.appendChild(head);

      const grid = el('div', 'tile-grid');
      let locked = false;
      item.options.forEach(opt => {
        const cell = el('button', 'tile');
        cell.appendChild(visual(opt));
        cell.onclick = async () => {
          if (locked) return;
          locked = true;
          const ok = opt.id === q.answer_id;
          if (ok) correct++;
          reportAnswer(q.answer_id, ok, 'story');
          markTile(cell, ok);
          feedback(ok);
          await playFx(ok);
          if (!ok) {
            const right = [...grid.children][item.options.findIndex(o => o.id === q.answer_id)];
            if (right) markTile(right, true);
            // переслушиваем предложение про верного героя — вот где был ответ
            const part = item.parts.find(p => p.word_id === q.answer_id);
            if (part) await playAudio(part.audio_url);
          }
          await sleep(500);
          qi++;
          if (qi < item.questions.length) {
            await askNext();
          } else {
            done({ scored: true, ok: correct === item.questions.length });
          }
        };
        grid.appendChild(cell);
      });
      zone.appendChild(grid);
      await playAudio(q.audio_url);
    };

    go.onclick = async () => {
      if (telling) return;
      btns.remove();               // история остаётся: это понимание, не память
      screen.appendChild(zone);
      await askNext();
    };

    await speakRu('Послушай историю');
    await sleep(150);
    tell();
  }


  async function rNegation(item, screen, done) {
    if (!introSeen('negation')) await showExerciseIntro('negation', screen);
    screen.innerHTML = '';
    // «Ул йөзәме?» — если на картинке другое действие, верный ответ «Юк, ул йөзми»
    screen.appendChild(el('div', 'instr', '🚫 Әйе или Юк?'));
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
      reportAnswer(item.word_id, ok, 'negation');
      feedback(ok); await playFx(ok);
      // верную фразу проговариваем всегда, ошибочную — никогда:
      // иначе ребёнок первым слышит неверный образец «Әйе, ул йөзә» под чужой картинкой
      await playAudio(item.is_match ? item.yes_audio : item.no_audio);
      await sleep(400);
      done({ scored: true, ok });
    };
    const yes = el('button', 'kid-btn yn-yes', '👍 Әйе');
    const no = el('button', 'kid-btn yn-no', '👎 Юк');
    yes.onclick = () => answer(true);
    no.onclick = () => answer(false);
    row.appendChild(yes); row.appendChild(no); screen.appendChild(row);
    speakThenPlay('Ответь на вопрос!', item.audio_url);
  }

  async function rWithWhat(item, screen, done) {
    if (!introSeen('with_what')) await showExerciseIntro('with_what', screen);
    screen.innerHTML = '';
    // «Нәрсә белән яза?» — выбери инструмент; ответ звучит целиком «Каләм белән»
    screen.appendChild(el('div', 'instr', '🛠 Чем это делают?'));
    const head = el('div', ''); head.style.cssText = 'display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:10px;';
    const play = el('button', 'play-btn small', '🔊');
    play.onclick = () => playAudio(item.audio_url);
    head.appendChild(play);
    const tw = el('div', 'word-big', item.text_tt);
    if ((item.text_tt || '').length > 16) tw.style.fontSize = '22px';
    head.appendChild(tw);
    screen.appendChild(head);
    const grid = el('div', 'tile-grid'); grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    screen.appendChild(grid);
    let locked = false;
    shuffled(item.options).forEach(opt => {
      const t = el('button', 'tile');
      t.appendChild(visual(opt));
      t.onclick = async () => {
        if (locked) return; locked = true;
        const ok = opt.id === item.word_id;
        reportAnswer(item.word_id, ok, 'with_what');
        t.classList.add(ok ? 'good' : 'bad');
        if (!ok) [...grid.children].forEach(c => { if (c._id === item.word_id) c.classList.add('good'); });
        feedback(ok); await playFx(ok);
        if (item.answer_audio) await playAudio(item.answer_audio);
        await sleep(350);
        done({ scored: true, ok });
      };
      t._id = opt.id;
      grid.appendChild(t);
    });
    speakThenPlay('Чем это делают?', item.audio_url);
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
    // у сводных сортировок («собери портфель», «по магазинам») свой заголовок
    screen.appendChild(el('div', 'instr', item.title
      ? `${item.title}: нажми картинку, потом корзинку`
      : '🧺 Разложи по корзинкам: нажми картинку, потом корзинку'));
    const basketsRow = el('div', 'baskets'); screen.appendChild(basketsRow);
    const itemsRow = el('div', 'sort-items'); screen.appendChild(itemsRow);
    let selected = null, wrong = 0, placed = 0, lockedAll = false;
    const baskets = {};
    item.baskets.forEach(b => {
      const bx = el('div', 'basket');
      bx.appendChild(el('span', 'icon', b.icon_emoji));
      // татарское имя корзины — крупно, русское мельче: ребёнку нужен звук,
      // взрослому рядом — понятная подпись
      if (b.title_tt) {
        const tt = el('div', '', b.title_tt);
        tt.style.cssText = 'font-weight:800;';
        bx.appendChild(tt);
        const ru = el('div', '', b.title_ru);
        ru.style.cssText = 'font-size:13px;opacity:.65;';
        bx.appendChild(ru);
      } else {
        bx.appendChild(el('div', '', b.title_ru));
      }
      bx.appendChild(el('div', 'caught', ''));
      bx.onclick = async () => {
        if (lockedAll) return;
        // тап по пустой корзине — озвучиваем её: по-татарски, если есть запись
        if (!selected) { if (b.audio_url) playAudio(b.audio_url); else speakRuBrowser(b.title_ru); return; }
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
    // у послелогов картинки нет намеренно: слово опознаётся только по звуку,
    // кнопка 🔊 становится крупной и единственной опорой
    if (item.image_url || item.emoji) {
      const vis = el('div', 'big-visual'); vis.appendChild(visual(item)); screen.appendChild(vis);
      const play = el('button', 'play-btn small', '🔊');
      play.style.margin = '0 auto'; play.style.display = 'block';
      play.onclick = () => playAudio(item.audio_url);
      screen.appendChild(play);
    } else {
      const play = el('button', 'play-btn', '🔊');
      play.style.cssText = 'margin:14px auto;display:block;';
      play.onclick = () => playAudio(item.audio_url);
      screen.appendChild(play);
    }
    const slots = el('div', 'slots'); screen.appendChild(slots);
    const letters = el('div', 'letters'); screen.appendChild(letters);
    const word = item.text_tt;
    // «дострой слово»: общий хвост уже стоит, собирается только различающееся начало
    const stemLen = item.stem_len || word.length;
    let pos = 0, wrong = 0;
    const slotEls = [...word].map((ch, i) => {
      const s = el('div', 'slot', '');
      if (i >= stemLen) { s.textContent = ch; s.classList.add('filled'); s.style.opacity = '.55'; }
      slots.appendChild(s);
      return s;
    });
    [...item.letters].forEach(ch => {
      const b = el('button', 'letter-tile', ch);
      b.onclick = async () => {
        if (ch === word[pos]) {
          slotEls[pos].textContent = ch; slotEls[pos].classList.add('filled');
          b.disabled = true; pos++;
          if (pos === stemLen) {
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
          if (wrong % 3 === 0) {
            // анти-тупик: подсказка сама ставит следующую букву
            const hintTile = [...letters.children].find(x => !x.disabled && x.textContent === word[pos]);
            if (hintTile) { hintTile.classList.add('good'); setTimeout(() => { hintTile.onclick(); hintTile.classList.remove('good'); }, 400); }
          }
        }
      };
      letters.appendChild(b);
    });
    speakThenPlay('Собери слово из букв', item.audio_url);
  }

  function rRepeatAfter(item, screen, done) {
    const w = item.word;
    screen.appendChild(el('div', 'instr', item.sentence_mode ? '🎤 Повтори предложение!' : '🎤 Повтори за диктором!'));
    const vis = el('div', 'big-visual'); vis.appendChild(visual(w)); screen.appendChild(vis);
    const twr = el('div', 'word-big', w.text_tt);
    if ((w.text_tt || '').length > 14) twr.style.fontSize = '24px';
    screen.appendChild(twr);
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
    // на http-адресе браузер вообще не даёт доступ к микрофону (нужен https)
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      mic.style.display = 'none';
      hint.textContent = 'Послушай диктора и повтори вслух! (запись голоса заработает на https-версии сайта)';
      showNext();
    }
    let starting = false;
    mic.onclick = async () => {
      if (recorder && recorder.state === 'recording') { recorder.stop(); return; }
      if (starting) return;   // второе касание, пока браузер ещё спрашивает разрешение
      starting = true;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec = new MediaRecorder(stream);
        recorder = rec;
        chunks = [];
        rec.ondataavailable = e => chunks.push(e.data);
        rec.onstop = () => {
          stream.getTracks().forEach(t => t.stop());
          mic.classList.remove('rec'); mic.textContent = '🎤';
          if (myUrl) URL.revokeObjectURL(myUrl);   // перезапись — старая ссылка больше не нужна
          myUrl = URL.createObjectURL(new Blob(chunks, { type: rec.mimeType || 'audio/webm' }));
          hint.textContent = 'Послушай себя и диктора — похоже?';
          showCompare();
        };
        rec.start();
        mic.classList.add('rec'); mic.textContent = '⏹';
        hint.textContent = 'Говори! Потом нажми ⏹';
        // таймаут привязан к СВОЕЙ записи: раньше он ссылался на общую переменную
        // и мог остановить следующую запись вместо своей
        setTimeout(() => { if (rec.state === 'recording') rec.stop(); }, 5000);
      } catch (e) {
        hint.textContent = 'Микрофон недоступен — просто повтори вслух!';
        showNext();
      }
      starting = false;
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
    // Кнопка одна на всё задание. Сюда приходят из трёх мест — нет микрофона,
    // отказ в разрешении и удачная запись, — и без этого флага ребёнок видел
    // «Получилось» столько раз, сколько раз нажимал на запись.
    let nextShown = false, finished = false;
    function showNext() {
      if (nextShown) return; nextShown = true;
      const next = el('button', 'kid-btn', 'Получилось! ➜');
      next.style.marginTop = '14px';
      next.onclick = () => {
        if (finished) return; finished = true;   // двойное касание не должно давать два ответа
        reportAnswer(w.id, true, 'repeat_after');
        done({ scored: false });
      };
      screen.appendChild(next);
      setTimeout(() => next.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
    }
    speakThenPlay('Повтори за диктором', w.audio_url);
  }

  const RENDERERS = {
    card: rCard,
    surprise_box: rSurpriseBox,
    shadow_reveal: rShadowReveal,
    color_reveal: rColorReveal,
    grow_reveal: rGrowReveal,
    pick_image: rPickImage,
    yes_no: rYesNo,
    question: rQuestion,
    alt_question: rAltQuestion,
    with_what: rWithWhat,
    negation: rNegation,
    plural: rPlural,
    story: rStory,
    where: rWhere,
    past: rPast,
    count: rCount,
    why: rWhy,
    dress: rDress,
    memory: rMemory,
    sort_baskets: rSortBaskets,
    pick_word_audio: rPickWordAudio,
    build_word: rBuildWord,
    build_sentence: rBuildSentence,
    repeat_after: rRepeatAfter,
    bubbles: rBubbles,
    feed: rFeed,
    who_ran: rWhoRan,
    moles: rMoles,
    windows: rWindows,
    flashlight: rFlashlight,
    chain: rChain,
    odd_one: rOddOne,
  };

  // ---------- раннер ----------
  async function run(container, opts) {
    container.innerHTML = '';
    const top = el('div', 'kid-top');
    const back = el('button', 'kid-back', '←');
    back.onclick = () => {
      // подтверждение выхода — случайный тап не должен терять урок
      if (document.getElementById('exit-confirm')) return;
      lessonPaused = true; // игры с авто-ходом (норки) и очередь done() замирают
      try { audioEl.pause(); ruAudioEl.pause(); speechSynthesis.cancel(); } catch (e) {}
      const overlay = el('div', '');
      overlay.id = 'exit-confirm';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:grid;place-items:center;z-index:70;padding:20px;';
      const box = el('div', 'kid-card');
      box.style.cssText = 'max-width:340px;width:100%;display:grid;gap:12px;text-align:center;';
      box.appendChild(el('div', 'word-big', 'Уйти с урока?'));
      const stay = el('button', 'kid-btn', '▶️ Продолжить');
      stay.onclick = () => { lessonPaused = false; overlay.remove(); };
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
        : opts.review
          ? await api(`/lesson/review/${opts.review}`)
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

    if (opts.review && data.empty) {
      screen.appendChild(el('div', 'sticker-award', '🎉'));
      screen.appendChild(el('div', 'word-big', 'Трудных слов нет — ты молодец!'));
      const back2 = el('button', 'kid-btn', '⬅ Назад');
      back2.style.marginTop = '14px';
      back2.onclick = () => location.href = opts.backUrl || '/static/pages/home.html';
      screen.appendChild(back2);
      speakRuBrowser('Трудных слов нет! Молодец!');
      return;
    }

    const items = data.items || [];
    // засекаем занятие: сервер видит только момент финиша, а между
    // открытием урока и первым ответом может пройти сколько угодно
    const startedAt = Date.now();
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
      renderer(item, screen, async (res) => {
        if (doneFired) return;
        doneFired = true;
        await waitUnpaused(); // не перескакивать задание, пока висит диалог выхода
        if (res && res.scored) {
          // каждое слово считается в знаменателе один раз; звезду даём, если ребёнок
          // в итоге ответил верно (первый раз или после переспроса) — не штрафуем за спотыкание
          if (!item._counted) {
            item._counted = true;
            total++;
            if (res.ok) {
              correct++;
            } else {
              item._requeued = true;
              items.push(item);      // то же задание вернётся в конце урока
              dots.appendChild(document.createElement('i'));
            }
          } else if (res.ok && !item._credited) {
            item._credited = true;   // переспрос пройден верно — добираем звезду, total уже учтён
            correct++;
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
      function stars_estimate() { return total > 0 && correct / total >= 0.85 ? 3 : (total > 0 && correct / total >= 0.65 ? 2 : 1); }
      let result;
      if (opts.review) {
        // тренировка — не влияет на карту/звёзды, только SRS-ответы уже записаны
        result = { stars: stars_estimate(), sticker: null, streak: 0 };
      } else {
        const payload = {
          kind: opts.daily ? 'daily' : 'unit',
          theme_id: opts.themeId || null,
          lesson_no: opts.lessonNo || null,
          correct, total,
          seconds: Math.round((Date.now() - startedAt) / 1000),
        };
        result = (await reportComplete(payload)) || { stars: stars_estimate(), sticker: null, streak: 0 };
      }
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

  // RENDERERS наружу — чтобы админ мог посмотреть ОДНО задание нужного типа
  // (_preview_ex.html), не проходя урок целиком ради редкого формата
  window.Lesson = { run, api, playAudio, speakRu, visual, el, confetti, RENDERERS };
})();
