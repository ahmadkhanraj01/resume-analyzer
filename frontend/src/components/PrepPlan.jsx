export default function PrepPlan({ days }) {
  return (
    <ol className="prep-plan">
      {days.map((day) => (
        <li key={day.day} className="prep-plan__day">
          <span className="prep-plan__marker" aria-hidden="true">
            {day.day}
          </span>
          <div className="prep-plan__body">
            <div className="prep-plan__heading">
              <span className="prep-plan__daylabel">Day {day.day}</span>
              {day.focus}
            </div>
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
