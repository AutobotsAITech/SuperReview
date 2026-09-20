const command = document.querySelector("#install-command");
const status = document.querySelector("#copy-status");
document.querySelectorAll('input[name="agent"]').forEach((input) => {
  input.addEventListener("change", () => {
    command.textContent = `npx skills add AutobotsAITech/SuperReview --skill superreview --agent ${input.value}`;
    status.textContent = "";
  });
});
document.querySelector("#copy-command").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(command.textContent);
    status.textContent = "Command copied.";
  } catch {
    status.textContent = "Select and copy the command above.";
  }
});
