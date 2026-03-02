const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const scoreEl = document.getElementById('score');
const bestScoreEl = document.getElementById('best-score');
const speedEl = document.getElementById('speed');
const messageEl = document.getElementById('message');

const CELL_SIZE = 24;
const GRID = canvas.width / CELL_SIZE;
const BASE_TICK_MS = 135;

let snake;
let direction;
let queuedDirection;
let food;
let score;
let bestScore = Number(localStorage.getItem('snake-best') || 0);
let state = 'idle';
let lastFrame = 0;
let tickMs = BASE_TICK_MS;

bestScoreEl.textContent = String(bestScore);

function resetGame() {
  snake = [
    { x: 8, y: 10 },
    { x: 7, y: 10 },
    { x: 6, y: 10 }
  ];
  direction = { x: 1, y: 0 };
  queuedDirection = direction;
  score = 0;
  scoreEl.textContent = '0';
  tickMs = BASE_TICK_MS;
  speedEl.textContent = '1x';
  spawnFood();
}

function spawnFood() {
  do {
    food = {
      x: Math.floor(Math.random() * GRID),
      y: Math.floor(Math.random() * GRID)
    };
  } while (snake.some((part) => part.x === food.x && part.y === food.y));
}

function setDirection(newDir) {
  if (state !== 'running') return;
  const opposite = direction.x === -newDir.x && direction.y === -newDir.y;
  if (!opposite) queuedDirection = newDir;
}

function startGame() {
  resetGame();
  state = 'running';
  messageEl.textContent = 'Stay alive.';
}

function gameOver() {
  state = 'gameover';
  if (score > bestScore) {
    bestScore = score;
    localStorage.setItem('snake-best', String(bestScore));
    bestScoreEl.textContent = String(bestScore);
  }
  messageEl.textContent = 'Game over. Press Enter to play again';
}

function update() {
  direction = queuedDirection;
  const head = { x: snake[0].x + direction.x, y: snake[0].y + direction.y };

  if (head.x < 0 || head.y < 0 || head.x >= GRID || head.y >= GRID) {
    gameOver();
    return;
  }

  if (snake.some((part) => part.x === head.x && part.y === head.y)) {
    gameOver();
    return;
  }

  snake.unshift(head);

  if (head.x === food.x && head.y === food.y) {
    score += 10;
    scoreEl.textContent = String(score);
    tickMs = Math.max(60, BASE_TICK_MS - Math.floor(score / 40) * 8);
    speedEl.textContent = `${(BASE_TICK_MS / tickMs).toFixed(1)}x`;
    spawnFood();
  } else {
    snake.pop();
  }
}

function drawCell(x, y, color) {
  ctx.fillStyle = color;
  ctx.fillRect(x * CELL_SIZE + 2, y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4);
}

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  drawCell(food.x, food.y, '#f94144');
  snake.forEach((part, idx) => {
    drawCell(part.x, part.y, idx === 0 ? '#88ff88' : '#22cc22');
  });

  if (state === 'paused') {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 40px Courier New';
    ctx.textAlign = 'center';
    ctx.fillText('PAUSED', canvas.width / 2, canvas.height / 2);
  }
}

function loop(timestamp) {
  if (state === 'running' && timestamp - lastFrame >= tickMs) {
    lastFrame = timestamp;
    update();
  }

  render();
  requestAnimationFrame(loop);
}

window.addEventListener('keydown', (event) => {
  const key = event.key.toLowerCase();

  if (key === 'enter' && state !== 'running') {
    startGame();
    return;
  }

  if (key === ' ' && state === 'running') {
    state = 'paused';
    messageEl.textContent = 'Paused. Press Space to continue';
    return;
  }

  if (key === ' ' && state === 'paused') {
    state = 'running';
    messageEl.textContent = 'Stay alive.';
    return;
  }

  const controls = {
    arrowup: { x: 0, y: -1 },
    w: { x: 0, y: -1 },
    arrowdown: { x: 0, y: 1 },
    s: { x: 0, y: 1 },
    arrowleft: { x: -1, y: 0 },
    a: { x: -1, y: 0 },
    arrowright: { x: 1, y: 0 },
    d: { x: 1, y: 0 }
  };

  if (controls[key]) {
    event.preventDefault();
    setDirection(controls[key]);
  }
});

resetGame();
render();
requestAnimationFrame(loop);
