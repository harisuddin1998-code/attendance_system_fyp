import { useCallback, useEffect, useRef, useState } from "react"

import { api } from "@/lib/api"

type Options = { interval?: number }
type State<T> = { path: string | null; data: T | null; error: string | null }

/** Fetch JSON from the API, optionally polling. Keeps showing the last data while refreshing. */
export function useApi<T>(path: string | null, { interval }: Options = {}) {
  const [state, setState] = useState<State<T>>({ path: null, data: null, error: null })
  const latestPath = useRef(path)

  useEffect(() => {
    latestPath.current = path
  }, [path])

  const reload = useCallback(async () => {
    if (!path) return
    try {
      const data = await api.get<T>(path)
      if (latestPath.current === path) setState({ path, data, error: null })
    } catch (e) {
      if (latestPath.current === path) setState((s) => ({ path, data: s.path === path ? s.data : null, error: (e as Error).message }))
    }
  }, [path])

  useEffect(() => {
    void reload()
    if (!interval) return
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void reload()
    }, interval)
    return () => window.clearInterval(id)
  }, [reload, interval])

  const current = state.path === path
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: !current,
    reload,
  }
}
