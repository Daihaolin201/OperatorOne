const dynamicPhrase = document.getElementById('dynamic-phrase');
const yearNode = document.getElementById('year');
const cursorGlow = document.querySelector('.cursor-glow');

if (yearNode) {
  yearNode.textContent = new Date().getFullYear();
}

const phrases = [
  '发现高价值机会',
  '快速生成并部署落地页',
  '打通 Marketing 到 Sales 的交接',
  '把反馈变成下一轮行动',
];
let phraseIndex = 0;

setInterval(() => {
  if (!dynamicPhrase) return;
  phraseIndex = (phraseIndex + 1) % phrases.length;
  dynamicPhrase.style.opacity = '0';
  setTimeout(() => {
    dynamicPhrase.textContent = phrases[phraseIndex];
    dynamicPhrase.style.opacity = '1';
  }, 180);
}, 2600);

if (cursorGlow) {
  window.addEventListener('pointermove', (event) => {
    cursorGlow.style.left = `${event.clientX}px`;
    cursorGlow.style.top = `${event.clientY}px`;
  });
}

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
      }
    });
  },
  {
    threshold: 0.14,
  }
);

document.querySelectorAll('.reveal').forEach((node) => revealObserver.observe(node));

let counted = false;
const metrics = document.querySelector('.metrics');

function animateCounter(node, target) {
  const duration = 1200;
  const start = performance.now();

  const tick = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    node.textContent = Math.floor(eased * target).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  };

  requestAnimationFrame(tick);
}

if (metrics) {
  const metricObserver = new IntersectionObserver(
    (entries) => {
      const entry = entries[0];
      if (entry.isIntersecting && !counted) {
        counted = true;
        document.querySelectorAll('[data-counter]').forEach((node) => {
          const target = Number(node.getAttribute('data-counter') || '0');
          animateCounter(node, target);
        });
      }
    },
    { threshold: 0.4 }
  );

  metricObserver.observe(metrics);
}

// Subtle 3D tilt cards
const tiltCards = document.querySelectorAll('.tilt-card');
const maxTilt = 7;

tiltCards.forEach((card) => {
  card.addEventListener('pointermove', (event) => {
    const rect = card.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const px = (x / rect.width) * 2 - 1;
    const py = (y / rect.height) * 2 - 1;

    card.style.transform = `perspective(900px) rotateY(${px * maxTilt}deg) rotateX(${py * -maxTilt}deg) translateY(-1px)`;
  });

  card.addEventListener('pointerleave', () => {
    card.style.transform = 'perspective(900px) rotateY(0deg) rotateX(0deg) translateY(0px)';
  });
});

// Animated particle network background
const canvas = document.getElementById('bg-canvas');
const ctx = canvas?.getContext('2d');

if (canvas && ctx) {
  const particles = [];
  let width = 0;
  let height = 0;

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function initParticles() {
    particles.length = 0;
    const count = Math.min(95, Math.max(42, Math.floor((width * height) / 24000)));

    for (let i = 0; i < count; i += 1) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        size: Math.random() * 2 + 0.8,
      });
    }
  }

  function step() {
    ctx.clearRect(0, 0, width, height);

    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0 || p.x > width) p.vx *= -1;
      if (p.y < 0 || p.y > height) p.vy *= -1;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(180, 201, 255, 0.7)';
      ctx.fill();
    }

    for (let i = 0; i < particles.length; i += 1) {
      for (let j = i + 1; j < particles.length; j += 1) {
        const a = particles[i];
        const b = particles[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distance = Math.hypot(dx, dy);

        if (distance < 128) {
          const opacity = (1 - distance / 128) * 0.32;
          ctx.strokeStyle = `rgba(117, 143, 255, ${opacity})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(step);
  }

  resize();
  initParticles();
  step();

  window.addEventListener('resize', () => {
    resize();
    initParticles();
  });
}
