import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import pl from '@/locales/pl.json'
import cs from '@/locales/cs.json'
import en from '@/locales/en.json'
import ko from '@/locales/ko.json'
import { useApp } from '@/state/store'

i18n.use(initReactI18next).init({
  resources: { pl: { translation: pl }, cs: { translation: cs }, en: { translation: en }, ko: { translation: ko } },
  lng: useApp.getState().lang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  returnObjects: true,
})

// Keep i18next and <html lang> in sync with the store.
document.documentElement.lang = useApp.getState().lang
useApp.subscribe((s, prev) => {
  if (s.lang !== prev.lang) {
    void i18n.changeLanguage(s.lang)
    document.documentElement.lang = s.lang
  }
})

export default i18n
