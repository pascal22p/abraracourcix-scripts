<?php
error_reporting(E_ALL);

function checkOverlaps(conn, from, to) {
  $sql = "SELECT COUNT(*) AS cpt FROM steps WHERE ?>fromdate AND ?<toDate OR ?>fromdate AND ?<toDate";
  $stmt->bind_param("ii", from, from, to, to);
  $result = $stmt->execute();
  return $result->fetch_object()->cpt > 0
}

$sql = "INSERT INTO steps (fromDate, toDate, steps, distance, floorsup, floorsdown) VALUES (?, ?, ?, ?, ?, ?)";

$steps = json_decode(file_get_contents('php://input'));

$user = $_SERVER['PHP_AUTH_USER'];
$password = $_SERVER['PHP_AUTH_PW'];
$database = $_GET['database'];

$conn = new mysqli('localhost', $user, $password, $database);
if ($conn->connect_error) {
  die("Connection failed: " . $conn->connect_error);
}

$stmt = $conn->prepare($sql);
$stmt->bind_param("iiiiii", $steps->from, $steps->to, $steps->steps, $steps->distance, $steps->floorsup, $steps->floorsdown);
$result = $stmt->execute();
$stmt->close();
$conn->close();

?>
