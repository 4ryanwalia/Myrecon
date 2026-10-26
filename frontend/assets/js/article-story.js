document.querySelectorAll('.story-checklist').forEach(list => {
  const update = () => {
    const total = list.querySelectorAll('input[type="checkbox"]').length;
    const done = list.querySelectorAll('input:checked').length;
    list.querySelector('output').textContent = `${done} of ${total} actions completed`;
  };
  list.addEventListener('change', update);
  update();
});
