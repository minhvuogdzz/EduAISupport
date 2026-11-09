import { AppShell } from "../../components/AppShell";
import { TeacherHeader } from "../teacher/TeacherHeader";
import { ENGLISH_SKILLS, ENGLISH_UNITS, SAMPLE_CLASS } from "./content";
import { LEVEL_TONE } from "./levels";
import "./subjects.css";

/** The teacher's view of the English preview: the draft topics as they are, and a labelled sample class. */
export function TeacherEnglishPage() {
  return (
    <AppShell>
      <title>Tiếng Anh · Monkey Edu</title>
      <TeacherHeader title="Tiếng Anh · Bản xem trước" />
      <div className="subject-page subject-page-teacher">
        <section aria-labelledby="teacher-topics-title">
          <h2 id="teacher-topics-title" className="subject-heading">
            Nội dung dự kiến
          </h2>
          <div className="subject-table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Chủ đề</th>
                  <th scope="col">Mục tiêu</th>
                  <th scope="col">Từ mới</th>
                  <th scope="col">Câu mẫu</th>
                  <th scope="col">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {ENGLISH_UNITS.map((unit) => (
                  <tr key={unit.id} className={unit.tone}>
                    <th scope="row" lang="en">
                      <span className="en-table-topic">
                        <span className="en-badge">
                          <unit.icon />
                        </span>
                        {unit.title}
                      </span>
                    </th>
                    <td>{unit.goal}</td>
                    <td>{unit.words.length}</td>
                    <td>{unit.phrases.length}</td>
                    <td>
                      <span className="level level-help">Bản nháp, chưa duyệt</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="teacher-class-title">
          <h2 id="teacher-class-title" className="subject-heading">
            Theo dõi lớp theo kỹ năng (minh họa)
          </h2>
          <p className="subject-text">Dữ liệu mẫu để xem bố cục, không phải học sinh thật.</p>
          <div className="subject-table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Học sinh</th>
                  {ENGLISH_SKILLS.map((skill) => (
                    <th scope="col" key={skill.name}>
                      {skill.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SAMPLE_CLASS.map((student) => (
                  <tr key={student.name}>
                    <th scope="row">{student.name}</th>
                    {student.levels.map((level, index) => (
                      <td key={ENGLISH_SKILLS[index].name}>
                        <span className={`level ${LEVEL_TONE[level]}`}>{level}</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
