import { useCallback, useEffect, useRef, useState } from "react"
import { CameraIcon, CameraOffIcon, ImageUpIcon, RotateCcwIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

type Props = {
  value: string | null
  onChange: (dataUrl: string | null) => void
  existingPhoto?: string | null
}

/** Capture a face from the webcam or an uploaded photo. Emits a JPEG data URL. */
export function FaceCapture({ value, onChange, existingPhoto }: Props) {
  const [mode, setMode] = useState<"camera" | "upload">("camera")
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [dragging, setDragging] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  // The <video> remounts after these actions, so reset its state alongside them.
  const errorMessage =
    cameraError ?? (navigator.mediaDevices ? null : "Camera isn't available in this browser. Upload a photo instead.")

  function changeMode(next: "camera" | "upload") {
    setReady(false)
    setCameraError(null)
    setMode(next)
  }

  function retake() {
    setReady(false)
    setCameraError(null)
    onChange(null)
  }

  useEffect(() => {
    if (mode !== "camera" || value) {
      stopCamera()
      return
    }
    let cancelled = false
    navigator.mediaDevices
      ?.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" } })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      })
      .catch((err: Error) => {
        setCameraError(
          err.name === "NotAllowedError"
            ? "Camera access was blocked. Allow it in your browser, or upload a photo instead."
            : "No camera found. Upload a photo instead."
        )
      })
    return () => {
      cancelled = true
      stopCamera()
    }
  }, [mode, value, stopCamera])

  function capture() {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement("canvas")
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext("2d")!.drawImage(video, 0, 0)
    onChange(canvas.toDataURL("image/jpeg", 0.92))
  }

  function readFile(file: File | undefined) {
    if (!file || !file.type.startsWith("image/")) return
    const reader = new FileReader()
    reader.onload = () => onChange(reader.result as string)
    reader.readAsDataURL(file)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Tabs value={mode} onValueChange={(v) => changeMode(v as "camera" | "upload")}>
          <TabsList>
            <TabsTrigger value="camera">
              <CameraIcon /> Camera
            </TabsTrigger>
            <TabsTrigger value="upload">
              <ImageUpIcon /> Upload
            </TabsTrigger>
          </TabsList>
        </Tabs>
        {value ? (
          <Button type="button" variant="ghost" size="sm" onClick={retake}>
            <RotateCcwIcon /> Retake
          </Button>
        ) : null}
      </div>

      <div
        className={cn(
          "relative aspect-[4/3] overflow-hidden rounded-xl ring-1 ring-foreground/10",
          mode === "camera" && !value && !errorMessage ? "bg-zinc-950" : "bg-muted"
        )}
      >
        {value ? (
          <img src={value} alt="Captured face" className="size-full object-cover" />
        ) : mode === "camera" ? (
          errorMessage ? (
            <div className="flex size-full flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground">
              <CameraOffIcon className="size-6" />
              {errorMessage}
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                onLoadedData={() => setReady(true)}
                className={cn("size-full -scale-x-100 object-cover transition-opacity duration-500", ready ? "opacity-100" : "opacity-0")}
              />
              {/* face guide */}
              {ready ? (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center animate-in fade-in-0 duration-500">
                  <div className="aspect-[3/4] h-[72%] rounded-[50%] shadow-[0_0_0_9999px_rgb(0_0_0/0.35)] ring-2 ring-white/70" />
                </div>
              ) : null}
              <div className="absolute inset-x-0 bottom-3 flex justify-center">
                <Button type="button" onClick={capture} disabled={!ready} className="rounded-full shadow-lg">
                  <CameraIcon /> Capture
                </Button>
              </div>
              {!ready ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-sm text-zinc-400">
                  <span className="size-6 animate-spin rounded-full border-2 border-zinc-700 border-t-zinc-300" />
                  Starting camera… allow access if your browser asks
                </div>
              ) : null}
            </>
          )
        ) : (
          <label
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              readFile(e.dataTransfer.files[0])
            }}
            className={cn(
              "flex size-full cursor-pointer flex-col items-center justify-center gap-2 border-2 border-dashed border-transparent p-6 text-center transition-colors",
              dragging && "border-primary bg-primary/5"
            )}
          >
            <span className="flex size-10 items-center justify-center rounded-full bg-background ring-1 ring-foreground/10">
              <ImageUpIcon className="size-5 text-muted-foreground" />
            </span>
            <span className="text-sm font-medium">Drop a photo or click to browse</span>
            <span className="text-xs text-muted-foreground">A clear, front-facing photo works best</span>
            <input type="file" accept="image/*" className="sr-only" onChange={(e) => readFile(e.target.files?.[0])} />
          </label>
        )}
      </div>
      {existingPhoto && !value ? (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <img src={existingPhoto} alt="" className="size-6 rounded-full object-cover" />
          A face is already enrolled. Capture a new one only to replace it.
        </p>
      ) : null}
    </div>
  )
}
