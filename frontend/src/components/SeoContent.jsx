const STEPS = [
  {
    title: 'Upload a video or paste a link',
    body: 'Drop in an MP4, MOV, MKV, AVI or WEBM file, or paste a YouTube (or other) video URL - no account needed.',
  },
  {
    title: 'AutoNote transcribes it',
    body: 'A local, open-source speech model turns the audio into a full transcript in the background.',
  },
  {
    title: 'AI writes detailed notes',
    body: 'The transcript is turned into structured, detailed notes - headings, bullet points, definitions and key takeaways.',
  },
  {
    title: 'Study with synced video, PDF & slides',
    body: 'Watch the video with notes that highlight in sync, swipe through concept slides, or download a designed PDF.',
  },
];

const FAQS = [
  {
    q: 'How do I convert a YouTube video to notes?',
    a: 'Paste the YouTube link into AutoNote and click "Generate my notes." AutoNote downloads the audio, transcribes it, and writes detailed notes you can read alongside the embedded video, then download as a PDF.',
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
