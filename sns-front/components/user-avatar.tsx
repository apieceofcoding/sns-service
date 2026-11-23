import { cn } from "@/lib/utils"

/** Profile image, or the first letter of the name when there is none. */
export function UserAvatar({
  username,
  imageUrl,
  className,
}: {
  username?: string
  imageUrl?: string | null
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#333639] font-bold text-foreground",
        className,
      )}
    >
      {imageUrl ? (
        <img src={imageUrl} alt={username ?? ""} className="size-full object-cover" />
      ) : (
        username?.charAt(0).toUpperCase()
      )}
    </div>
  )
}
