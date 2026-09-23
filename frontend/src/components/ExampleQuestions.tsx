const EXAMPLES = [
  'Which building had the highest electricity consumption?',
  "How did B007's consumption change from July to August 2024?",
  'Compare B001 and B007 in July 2024.',
  "Show B007's monthly consumption from January to June 2024.",
  'Are there any anomalous energy readings?',
];

interface ExampleQuestionsProps {
  onSelect: (question: string) => void;
  disabled: boolean;
}

export function ExampleQuestions({ onSelect, disabled }: ExampleQuestionsProps) {
  return (
    <div className="example-questions">
      <h3>Example questions</h3>
      <ul>
        {EXAMPLES.map((q) => (
          <li key={q}>
            <button
              onClick={() => onSelect(q)}
              disabled={disabled}
              type="button"
            >
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
