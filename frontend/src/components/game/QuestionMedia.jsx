
function QuestionMedia({ type, url }) {
  if (!url || type === "text") {
    return null;
  }

  return (
    <div className="flex h-44 w-full items-center justify-center overflow-hidden rounded-2xl border border-purple-400/20 bg-black/30 sm:h-52">
      {type === "image" && (
        <img
          src={url}
          alt="Question media"
          className="h-full w-full object-contain"
        />
      )}

      {type === "audio" && (
        <audio controls className="w-full px-3">
          <source src={url} />
          Your browser does not support audio.
        </audio>
      )}

      {type === "youtube" && (
  <iframe
    className="h-full w-full"
    src={`https://www.youtube.com/embed/${new URL(url).pathname.split("/").filter(Boolean).pop()}`}
    title="Quiz question video"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    allowFullScreen
  />
)}
    </div>
  );
}

export default QuestionMedia;
