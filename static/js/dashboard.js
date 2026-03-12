document.addEventListener("DOMContentLoaded", function() {

  var data = window.dashboard_data || {};

  var followers = data.followers || 0;
  var following = data.following || 0;
  var likes     = data.likes    || 0;
  var comments  = data.comments || 0;

  createRelationshipChart(followers, following);
  createInteractionChart(likes, comments);

});