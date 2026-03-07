const workflowForm = document.getElementById("workflow-form");
const workflowResult = document.getElementById("workflow-result");
const signupForm = document.getElementById("signup-form");
const signupResult = document.getElementById("signup-result");

workflowForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  workflowResult.textContent = "Generating first step...";

  const input = document.getElementById("input")?.value?.trim() || "";
  if (input.length < 8) {
    workflowResult.textContent = "Please provide a bit more detail so the workflow can route correctly.";
    return;
  }

  try {
    const response = await fetch("/api/first-step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input }),
    });

    const data = await response.json();
    if (!response.ok) {
      workflowResult.textContent = data?.error || "Failed to generate first step.";
      return;
    }

    const lines = [
      `First step: ${data.first_step}`,
      "",
      `Matched rule: ${data.rule_id || "default"}`,
      "",
      "Next steps:",
      ...(data.next_steps || []).map((item, idx) => `${idx + 1}. ${item}`),
    ];
    workflowResult.textContent = lines.join("\n");
  } catch (error) {
    workflowResult.textContent = `Error: ${error.message}`;
  }
});

signupForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  signupResult.textContent = "Submitting...";

  const email = document.getElementById("email")?.value?.trim() || "";
  try {
    const response = await fetch("/api/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, source: "web-cta" }),
    });
    const data = await response.json();

    if (!response.ok) {
      signupResult.textContent = data?.error || "Could not submit.";
      return;
    }

    signupResult.textContent = data.message || "Thanks, you're on the pilot list.";
  } catch (error) {
    signupResult.textContent = `Error: ${error.message}`;
  }
});
