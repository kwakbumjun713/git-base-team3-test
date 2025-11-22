const changeSound = new Audio('/static/sound/change.mp3')
const dropSound = new Audio('/static/sound/drop.mp3')
const breakSound = new Audio('/static/sound/break.mp3')

export function playChange() {
  playSound(changeSound)
}
export function playDrop() {
  playSound(dropSound)
}
export function playBreak() {
  playSound(breakSound)
}

function playSound(sound) {
  sound.currentTime = 0
  sound.play()
}
function stopSound(sound) {
  sound.pause()
}
