type SpeechWindow = Window & {
  webkitAudioContext?: typeof AudioContext;
};

const EMERGENCY_TONE_FREQUENCIES = [880, 660];
export const OFFICIAL_POLICE_HELP_URL = 'https://cyberpolice.mps.gov.cn/wfjb/html/index.shtml';

export const sanitizePhoneNumber = (value?: string | null) => {
  return (value ?? '').replace(/[^\d+]/g, '');
};

export const callPhoneNumber = (value?: string | null) => {
  const number = sanitizePhoneNumber(value);
  if (!number) {
    return false;
  }

  window.location.href = `tel:${number}`;
  return true;
};

export const openOfficialPoliceHelpPage = () => {
  const nextWindow = window.open(OFFICIAL_POLICE_HELP_URL, '_blank', 'noopener,noreferrer');
  if (nextWindow) {
    nextWindow.opener = null;
    return true;
  }

  window.location.href = OFFICIAL_POLICE_HELP_URL;
  return true;
};

export const playWarningTone = () => {
  const speechWindow = window as SpeechWindow;
  const AudioContextCtor = window.AudioContext ?? speechWindow.webkitAudioContext;
  if (!AudioContextCtor) {
    return;
  }

  const audioContext = new AudioContextCtor();
  const gainNode = audioContext.createGain();
  gainNode.gain.value = 0.08;
  gainNode.connect(audioContext.destination);

  EMERGENCY_TONE_FREQUENCIES.forEach((frequency, index) => {
    const oscillator = audioContext.createOscillator();
    const startAt = audioContext.currentTime + index * 0.28;
    oscillator.type = 'sine';
    oscillator.frequency.value = frequency;
    oscillator.connect(gainNode);
    oscillator.start(startAt);
    oscillator.stop(startAt + 0.18);
  });

  window.setTimeout(() => {
    void audioContext.close();
  }, 900);
};

export const speakWarning = (text: string, lang: 'zh-CN' | 'en-US') => {
  if (!('speechSynthesis' in window) || !text.trim()) {
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = 0.92;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
};

export const triggerVoiceWarning = (text: string, lang: 'zh-CN' | 'en-US') => {
  playWarningTone();
  window.setTimeout(() => speakWarning(text, lang), 220);
};
