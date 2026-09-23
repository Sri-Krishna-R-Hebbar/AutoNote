const STEPS = [
  {
    title: 'Upload a video',
    body: 'Drop in an MP4, MOV, MKV, AVI or WEBM file - no account needed. Got a YouTube link instead? Download it with a tool like YTUltra first (pick a version with audio), then upload the file here.',
  },
  {
    title: 'AutoNote reads both the audio and the screen',
    body: 'A local, open-source speech model transcribes what was said, while a vision AI scans video frames for anything written, typed, or drawn on screen - slides, whiteboards, code, handwriting - including things never spoken aloud.',
  },
  {
    title: 'AI writes detailed notes',
    body: 'Both sources are merged into structured, detailed notes - headings, bullet points, definitions and key takeaways.',
  },
  {
    title: 'Study with synced video, PDF & slides',
    body: 'Watch the video with notes that highlight in sync, swipe through concept slides, or download a designed PDF.',
  },
];

const FAQS = [
  {
    q: 'How do I convert a YouTube video to notes?',
    a: 'Download the video first with a tool like YTUltra (choosing a version that includes audio), then upload the downloaded file to AutoNote and click "Generate my notes." AutoNote transcribes it and writes detailed notes you can read alongside the video, then download as a PDF.',
  },
  {
    q: 'Can I turn any video into notes, not just YouTube?',
    a: 'Yes. You can upload your own video file (lecture recordings, meeting recordings, webinars) in MP4, MOV, MKV, AVI or WEBM format, and AutoNote will generate the same detailed notes and PDF.',
  },
  {
    q: 'Is AutoNote free to use?',
    a: 'Yes, AutoNote is free to use. It runs on free-tier AI services and a local open-source speech model.',
  },
  {
    q: 'What do I get besides the PDF?',
    a: 'A Studio view with the video playing alongside notes that auto-highlight the current section, plus a swipeable Concept Slides deck summarizing key points - in addition to the downloadable PDF.',
  },
  {
    q: 'Does it pick up things written on screen but never said out loud?',
    a: 'Yes. Alongside transcribing speech, AutoNote samples video frames and uses a vision AI to read slides, whiteboard writing, handwritten notes, code, and diagrams, then merges that with the transcript - so notes capture content a presenter wrote down but didn’t narrate.',
  },
  {
    q: 'Can I upload video and audio separately?',
    a: 'Yes. If you downloaded a video-only file and a separate audio-only file (common with some YouTube downloaders), upload both - AutoNote will transcribe the audio and analyze the video’s on-screen content together. Only have one of them? That works too.',
  },
];

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQS.map((item) => ({
    '@type': 'Question',
    name: item.q,
    acceptedAnswer: { '@type': 'Answer', text: item.a },
  })),
};

export default function SeoContent() {
  return (
    <section className="seo-content" aria-labelledby="how-it-works-heading">
      <div className="seo-block">
        <h2 id="how-it-works-heading">How to turn a video into notes</h2>
        <ol className="how-steps">
          {STEPS.map((step) => (
            <li key={step.title}>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </li>
          ))}
        </ol>
      </div>

      <div className="seo-block">
        <h2>Frequently asked questions</h2>
        <div className="faq-list">
          {FAQS.map((item) => (
            <details key={item.q}>
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>

      {/* eslint-disable-next-line react/no-danger */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
    </section>
  );
}
