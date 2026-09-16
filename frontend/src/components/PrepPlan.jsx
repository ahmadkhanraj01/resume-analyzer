export default function PrepPlan({ days }) {
  return (
    <ol className="prep-plan">
      {days.map((day) => (
        <li key={day.day} className="prep-plan__day">
          <div className="prep-plan__heading">
            Day {day.day}: {day.focus}
          </div>
          <ul className="prep-plan__tasks">
            {day.tasks.map((task, i) => (
              <li key={i}>{task}</li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
