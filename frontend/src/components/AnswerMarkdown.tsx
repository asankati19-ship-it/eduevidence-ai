import Markdown from 'react-markdown';

const FORMATTING = [
  'p', 'strong', 'em', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'hr',
];

export function AnswerMarkdown({ body }: { body: string }) {
  return <div className="answer-body">
    <Markdown skipHtml allowedElements={FORMATTING} unwrapDisallowed components={{
      h1: ({ children }) => <h3>{children}</h3>,
      h2: ({ children }) => <h3>{children}</h3>,
      h3: ({ children }) => <h4>{children}</h4>,
      h4: ({ children }) => <h4>{children}</h4>,
      h5: ({ children }) => <h4>{children}</h4>,
      h6: ({ children }) => <h4>{children}</h4>,
    }}>{body}</Markdown>
  </div>;
}

