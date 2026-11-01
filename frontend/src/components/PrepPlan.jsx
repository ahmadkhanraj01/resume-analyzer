export default function PrepPlan({ days }) {
  return (
    <ol className="prep-plan">
      {days.map((day) => (
        <li key={day.day} className="prep-plan__day">
          <span className="prep-plan__marker">
            <span className="prep-plan__marker-word">Day</span> {day.day}
          </span>
          <div className="prep-plan__body">
            <div className="prep-plan__heading">{day.focus}</div>
            <ul className="prep-plan__tasks">
              {day.tasks.map((task, i) => (
                <li key={i}>{task}</li>
              ))}
            </ul>
          </div>
        </li>
      ))}
    </ol>
  );
}
