<?php
error_reporting(0);
ini_set("log_errors", 1);
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

$sql = "INSERT INTO locations (acc, alt, lat, lon, tid, tst, vac, vel, p, user) VALUES (?, ?, ?, ?, ?, FROM_UNIXTIME(?), ?, ?, ?, ?)";

$location = json_decode(file_get_contents('php://input'));

$user = $_SERVER['PHP_AUTH_USER'];
$password = $_SERVER['PHP_AUTH_PW'];
$database = $_GET['database'];

$conn = new mysqli('localhost', $user, $password, $database);
if ($conn->connect_error) {
  error_log("Connection failed: " . $conn->connect_error);
  die("Connection failed: " . $conn->connect_error);
}

try {
  $stmt = $conn->prepare($sql);
  if(property_exists($location, 'vel')) {
    $vel = $location->vel;
  } else {
    $vel = 0;
  }
  $stmt->bind_param("iiddsiiids", $location->acc, $location->alt, $location->lat, $location->lon, $location->tid, $location->tst, $location->vac, $vel, $location->p, $location->user);
  $result = $stmt->execute();
  echo "Success";
  http_response_code(200);
} catch (Exception $e) {
    if ($stmt->errno == 1062) {
      echo "duplicated";
      http_response_code(422);
    } else {
      error_log('Caught exception: ('.strval($stmt->errno).') '.  $e->getMessage());
      echo 'Caught exception: '.  $e->getMessage();
      http_response_code(500);
      exit();
   }
}
$stmt->close();
$conn->close();

?>
