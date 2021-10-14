<?php
error_reporting(0);
ini_set("log_errors", 1);
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

function checkOverlaps($conn, $from, $to) {
  $sql = "SELECT COUNT(*) AS cpt FROM steps WHERE ?>fromdate AND ?<toDate OR ?>fromdate AND ?<toDate";
  $stmt->bind_param("iiii", $from, $from, $to, $to);
  $result = $stmt->execute();
  return $result->fetch_object()->cpt > 0;
}

$sql = "REPLACE INTO steps (fromDate, toDate, steps, distance, floorsup, floorsdown, user) VALUES (FROM_UNIXTIME(?), FROM_UNIXTIME(?), ?, ?, ?, ?, ?)";

$steps = json_decode(file_get_contents('php://input'));

$user = $_SERVER['PHP_AUTH_USER'];
$password = $_SERVER['PHP_AUTH_PW'];
$database = $_GET['database'];

$conn = new mysqli('localhost', $user, $password, $database);
if ($conn->connect_error) {
  die("Connection failed: " . $conn->connect_error);
}

try {
  $stmt = $conn->prepare($sql);
  $stmt->bind_param("iiiiiis", $steps->from, $steps->to, $steps->steps, $steps->distance, $steps->floorsup, $steps->floorsdown, $steps->user);
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
   }
}

$stmt->close();
$conn->close();

?>
