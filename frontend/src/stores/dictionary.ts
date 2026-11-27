/** The shared word dictionary (Smart Tools › Word Dictionary), loaded once signed in. */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listDictionaryWords, type DictionaryWord } from '@/wordDictionary'

export const useDictionaryStore = defineStore('dictionary', () => {
  const words = ref<DictionaryWord[]>([])

  async function load() {
    try {
      words.value = await listDictionaryWords()
    } catch {
      // Without the dictionary nothing is replaced
    }
  }

  return { words, load }
})
