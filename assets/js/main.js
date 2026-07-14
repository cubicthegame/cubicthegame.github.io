// ===== Navbar scroll state =====
const navbar = document.querySelector('.navbar');
const navLogo = document.querySelector('.nav-center img');
const heroLogo = document.querySelector('.hero-logo');

function onScroll(){
  if (!navbar) return;
  const y = window.scrollY;
  navbar.classList.toggle('is-scrolled', y > 8);

  if (heroLogo && navLogo){
    const rect = heroLogo.getBoundingClientRect();
    // fade the small nav logo in as the big hero logo scrolls out of view
    const threshold = window.innerHeight * 0.25;
    navLogo.classList.toggle('is-visible', rect.bottom < threshold);
  }
}
window.addEventListener('scroll', onScroll, { passive:true });
onScroll();

// ===== Language switch =====
const STRINGS = {
  en: {
    nav_news: "News", nav_presskit: "Press Kit", nav_wishlist: "Wishlist now!",
    hero_tag: "A melancholic isometric puzzle adventure across the last lands of a fallen world.",
    demo_cta: "Play the DEMO now on Steam",
    feat1_title: "Explore what remains",
    feat1_body: "Map out disparate lands and overcome their unique challenges.\nImmerse yourself in the calm and melancholic atmosphere of what remains.\nUncover the secrets and treasures of humanity's final descendants.",
    feat2_title: "Simple rules, deep puzzles",
    feat2_body: "Enjoy a minimalistic ruleset that's easy to learn and fun to master.\nSolve deeper and deeper puzzles, as simple rules combine into surprising results.\nChoose your own path and engage at your own pace.",
    screenshots_title: "Screenshots",
    news_title: "Latest news",
    view_all: "View all",
    subscribe_title: "Subscribe to our newsletter",
    subscribe_body: "Devlogs, patch notes and the occasional turtle. No spam, unsubscribe any time.",
    subscribe_placeholder: "you@example.com",
    subscribe_button: "Subscribe",
    subscribe_success: "Thanks — check your inbox to confirm.",
    footer_contact: "Contact",
    footer_legal: "Legal",
    footer_terms: "Terms of Service",
    footer_privacy: "Privacy Policy",
    footer_steam: "Steam Page",
    footer_rights: "All rights reserved."
  },
  da: {
    nav_news: "Nyheder", nav_presskit: "Presseki t", nav_wishlist: "Ønsk dig den nu!",
    hero_tag: "Et melankolsk, isometrisk puslespilseventyr gennem de sidste lande i en falden verden.",
    demo_cta: "Spil DEMOEN nu på Steam",
    feat1_title: "Udforsk det, der er tilbage",
    feat1_body: "Kortlæg forskellige lande og overvind deres unikke udfordringer.\nFordyb dig i den rolige og melankolske stemning af det, der er tilbage.\nAfdæk hemmeligheder og skatte fra menneskehedens sidste efterkommere.",
    feat2_title: "Simple regler, dybe gåder",
    feat2_body: "Nyd et minimalistisk regelsæt, der er let at lære og sjovt at mestre.\nLøs stadig dybere gåder, når enkle regler kombineres til overraskende resultater.\nVælg din egen vej, og spil i dit eget tempo.",
    screenshots_title: "Skærmbilleder",
    news_title: "Seneste nyheder",
    view_all: "Se alle",
    subscribe_title: "Tilmeld dig vores nyhedsbrev",
    subscribe_body: "Devlogs, patch notes og en enkelt skildpadde. Ingen spam — afmeld når som helst.",
    subscribe_placeholder: "dig@eksempel.dk",
    subscribe_button: "Tilmeld",
    subscribe_success: "Tak — bekræft venligst via din indbakke.",
    footer_contact: "Kontakt",
    footer_legal: "Juridisk",
    footer_terms: "Servicevilkår",
    footer_privacy: "Privatlivspolitik",
    footer_steam: "Steam-side",
    footer_rights: "Alle rettigheder forbeholdes."
  }
};

function applyLang(lang){
  const dict = STRINGS[lang] || STRINGS.en;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] !== undefined) el.textContent = dict[key];
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (dict[key] !== undefined) el.setAttribute('placeholder', dict[key]);
  });
  document.documentElement.setAttribute('lang', lang);
  localStorage.setItem('cubic-lang', lang);
  document.querySelectorAll('.lang-menu button').forEach(b=>{
    b.setAttribute('aria-selected', b.dataset.lang === lang ? 'true' : 'false');
  });
  const label = document.querySelector('.lang-current');
  if (label) label.textContent = lang.toUpperCase();
}

const langBtn = document.querySelector('.lang-btn');
const langMenu = document.querySelector('.lang-menu');
if (langBtn && langMenu){
  langBtn.addEventListener('click', (e)=>{
    e.stopPropagation();
    langMenu.classList.toggle('is-open');
  });
  document.addEventListener('click', ()=> langMenu.classList.remove('is-open'));
  langMenu.querySelectorAll('button').forEach(b=>{
    b.addEventListener('click', ()=> applyLang(b.dataset.lang));
  });
}
applyLang(localStorage.getItem('cubic-lang') || 'en');

// ===== Trailer: click-to-load embed (perf + avoids extra 3rd-party requests until needed) =====
document.querySelectorAll('.video-thumb').forEach(thumb=>{
  thumb.addEventListener('click', ()=>{
    const id = thumb.dataset.youtubeId;
    const wrap = thumb.closest('.video-wrap').querySelector('.ratio');
    const iframe = document.createElement('iframe');
    iframe.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1`;
    iframe.title = "Cubic — Official Trailer";
    iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    wrap.innerHTML = '';
    wrap.appendChild(iframe);
  });
});

// ===== Screenshot carousel =====
const track = document.querySelector('.carousel-track');
if (track){
  const prevBtn = document.querySelector('.carousel-controls .prev');
  const nextBtn = document.querySelector('.carousel-controls .next');
  const scrollAmount = () => track.querySelector('img')?.clientWidth + 16 || 300;
  prevBtn?.addEventListener('click', ()=> track.scrollBy({left:-scrollAmount(), behavior:'smooth'}));
  nextBtn?.addEventListener('click', ()=> track.scrollBy({left:scrollAmount(), behavior:'smooth'}));
}

// ===== Subscribe form (static hosting: hook up to your provider, e.g. Mailchimp/Buttondown) =====
const subForm = document.querySelector('.subscribe-form');
if (subForm){
  subForm.addEventListener('submit', (e)=>{
    e.preventDefault();
    const success = document.querySelector('.subscribe-success');
    // TODO: wire this up to a real newsletter provider endpoint.
    if (success) success.style.display = 'block';
    subForm.reset();
  });
}
